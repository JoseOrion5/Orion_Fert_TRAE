import argparse
import os
import sqlite3
import pandas as pd
import re
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

def _default_base_dir() -> Path:
    env = (os.getenv("ORION_BASE_DIR") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parent


BASE_DIR = _default_base_dir()
EXCEL_PATH_BASE = Path(os.getenv("ORION_EXCEL_BASE") or (BASE_DIR / "COMPLETAO" / "2-BASE_UNICA_COM_PRECOS_E_MAX_INFO_COM_FONTES.xlsx"))
EXCEL_PATH_COMPLETAO = Path(os.getenv("ORION_EXCEL_COMPLETAO") or (BASE_DIR / "COMPLETAO" / "COMPLETAO.xlsx"))
DB_PATH = Path(os.getenv("ORION_DB_PATH") or (BASE_DIR / "orion_agroquim.db"))

def _safe_float(value):
    if value is None: return 0.0
    s = str(value).strip().replace("%", "").replace(",", ".")
    try:
        v = float(s)
        return v if math.isfinite(v) else 0.0
    except ValueError: return 0.0

def _clean_price(value):
    if value is None: return 0.0
    s = str(value).strip().upper()
    if s in {"", "NAN", "NONE", "NULL", "-"}: return 0.0
    s = s.replace("US$", "").replace("USD", "").replace("R$", "").replace("$", "").replace("BRL", "").strip()
    s = s.replace(",", ".")
    try:
        v = float(s)
        return v if math.isfinite(v) else 0.0
    except ValueError: return 0.0

def create_schema(conn):
    cursor = conn.cursor()
    
    # Tabela de Insumos
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS insumos (
        id TEXT PRIMARY KEY,
        nome TEXT NOT NULL,
        solubilidade TEXT,
        natureza_fisica TEXT,
        preco_unit REAL DEFAULT 0.0,
        fornecedor TEXT,
        fator_v REAL DEFAULT 0.5,
        rank_solubilidade INTEGER DEFAULT 3,
        rank_custo INTEGER DEFAULT 3
    )
    ''')

    # Tabela de Teores (Nutrientes por Insumo)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS teores (
        insumo_id TEXT,
        nutriente TEXT,
        valor REAL,
        PRIMARY KEY (insumo_id, nutriente),
        FOREIGN KEY (insumo_id) REFERENCES insumos (id)
    )
    ''')

    # Tabela de Aditivos
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS aditivos (
        id TEXT PRIMARY KEY,
        nome TEXT NOT NULL,
        abreviatura TEXT,
        categoria TEXT,
        funcao TEXT,
        nutrientes_compativeis TEXT,
        ph_ideal TEXT,
        dose_legal TEXT,
        dose_tecnica TEXT,
        setup TEXT,
        alerta TEXT,
        observacoes TEXT,
        preco_unit REAL DEFAULT 0.0,
        hlb REAL DEFAULT 0.0,
        limite_forca_ionica REAL DEFAULT 0.0,
        tipo_reologia TEXT DEFAULT ''
    )
    ''')

    # Tabela de POP (Procedimento Operacional Padrão)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS processos_pop (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        etapa TEXT,
        procedimento TEXT,
        notas TEXT
    )
    ''')

    # Tabela de PCC (Pontos Críticos de Controle)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS processos_pcc (
        id TEXT PRIMARY KEY,
        parametro TEXT,
        limite TEXT,
        acao TEXT
    )
    ''')

    conn.commit()

def _ensure_aditivos_extra_columns(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(aditivos)")
    cols = {str(r[1]) for r in (cur.fetchall() or [])}
    for name, ddl in [
        ("hlb", "ALTER TABLE aditivos ADD COLUMN hlb REAL DEFAULT 0.0"),
        ("limite_forca_ionica", "ALTER TABLE aditivos ADD COLUMN limite_forca_ionica REAL DEFAULT 0.0"),
        ("tipo_reologia", "ALTER TABLE aditivos ADD COLUMN tipo_reologia TEXT DEFAULT ''"),
    ]:
        if name not in cols:
            cur.execute(ddl)
    conn.commit()

def _parse_price_range_to_float(value: Any) -> float:
    s = str(value or "").strip()
    if not s or s.lower() in {"nan", "none", "null", "-"}:
        return 0.0
    s = s.replace("US$", "").replace("USD", "").replace("$", "").strip()
    s = s.replace(",", ".")
    m = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*-\s*([0-9]+(?:\.[0-9]+)?)\s*$", s)
    if m:
        try:
            a = float(m.group(1))
            b = float(m.group(2))
            if math.isfinite(a) and math.isfinite(b):
                return float((a + b) / 2.0)
        except Exception:
            return 0.0
    try:
        v = float(s)
        return float(v) if math.isfinite(v) else 0.0
    except Exception:
        mm = re.search(r"[-+]?\d*\.\d+|\d+", s)
        if not mm:
            return 0.0
        try:
            v = float(mm.group())
            return float(v) if math.isfinite(v) else 0.0
        except Exception:
            return 0.0

def _norm_key(s: str) -> str:
    s = (s or "").strip().casefold()
    table = str.maketrans({"á": "a", "à": "a", "â": "a", "ã": "a", "ä": "a", "é": "e", "ê": "e", "ë": "e", "í": "i", "ï": "i", "ó": "o", "ô": "o", "õ": "o", "ö": "o", "ú": "u", "ü": "u", "ç": "c"})
    return s.translate(table)

def _abbr_from_name(name: str) -> str:
    s = str(name or "").strip()
    m = re.search(r"\(([^)]+)\)", s)
    if m:
        cand = m.group(1).strip()
        if re.fullmatch(r"[A-Za-z0-9\-]{2,12}", cand):
            return cand.upper()
    tokens = re.findall(r"[A-Za-z0-9]+", s)
    up = [t for t in tokens if any(c.isalpha() for c in t) and t.isupper() and 2 <= len(t) <= 10]
    if up:
        return up[0]
    words = [w for w in re.split(r"[\s\-_/]+", s) if w]
    abbr = "".join([w[0].upper() for w in words[:6] if w[0].isalpha()])
    return abbr[:8]

def _infer_hlb_limit_rheo(name: str) -> Tuple[float, float, str]:
    key = _norm_key(name)
    hlb_ref = {
        _norm_key("Tween 80"): 15.0,
        _norm_key("Polissorbato 80"): 15.0,
        _norm_key("Span 80"): 4.3,
        _norm_key("Nonilfenol 9.5 EO"): 13.0,
    }
    if key in hlb_ref:
        return float(hlb_ref[key]), 0.0, ""

    if "xantana" in key:
        return 0.0, 0.8, "Não-Newtoniano"
    if "cmc" in key or "carboximetilcelulose" in key:
        return 0.0, 0.4, "Não-Newtoniano"
    if "attapulgita" in key or "atapulgita" in key or "bentonita" in key:
        return 0.0, 9999.0, "Não-Newtoniano"
    return 0.0, 0.0, ""

def import_aditivos_from_markdown(conn: sqlite3.Connection, md_path: Path) -> int:
    if not md_path.exists():
        raise FileNotFoundError(str(md_path))

    txt = md_path.read_text(encoding="utf-8", errors="replace").splitlines()
    base_idx = next((i for i, ln in enumerate(txt) if ln.strip() == "## Base_Geral"), None)
    if base_idx is None:
        raise RuntimeError("Seção '## Base_Geral' não encontrada no Markdown.")

    table_lines: List[str] = []
    for ln in txt[base_idx + 1:]:
        if ln.strip().startswith("|"):
            table_lines.append(ln.rstrip("\n"))
            continue
        if table_lines:
            break

    if len(table_lines) < 3:
        raise RuntimeError("Tabela Markdown de Base_Geral não encontrada ou vazia.")

    header = [c.strip() for c in table_lines[0].strip("|").split("|")]
    want = ["Classe", "Aditivo", "Aplicação", "US$/kg_aprox", "US$/L_aprox", "Forma_típica", "Observações"]
    if [_norm_key(h) for h in header] != [_norm_key(w) for w in want]:
        raise RuntimeError(f"Cabeçalho inesperado em Base_Geral. Esperado: {want}. Encontrado: {header}.")

    cur = conn.cursor()
    inserted = 0
    for ln in table_lines[2:]:
        parts = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(parts) < 7:
            continue
        if len(parts) > 7:
            parts = parts[:6] + [" | ".join(parts[6:]).strip()]
        classe, aditivo_nome, aplicacao, usdkg, _usdl, forma, obs = parts
        if not aditivo_nome or aditivo_nome.lower() == "nan":
            continue

        preco = _parse_price_range_to_float(usdkg)
        abbr = _abbr_from_name(aditivo_nome)
        hlb, lim_i, rheo = _infer_hlb_limit_rheo(aditivo_nome)

        cur.execute(
            """
            INSERT OR REPLACE INTO aditivos
            (id, nome, abreviatura, categoria, funcao, nutrientes_compativeis, ph_ideal, dose_legal, dose_tecnica, setup, alerta, observacoes, preco_unit, hlb, limite_forca_ionica, tipo_reologia)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                aditivo_nome,
                aditivo_nome,
                abbr,
                classe,
                aplicacao,
                "",
                "",
                "",
                "",
                forma,
                "",
                obs,
                float(preco or 0.0),
                float(hlb or 0.0),
                float(lim_i or 0.0),
                str(rheo or ""),
            ),
        )
        inserted += 1

    conn.commit()
    return inserted

def migrate_insumos(conn):
    print("Migrando Insumos de BASE_UNICA...")
    try:
        df = pd.read_excel(EXCEL_PATH_BASE, sheet_name="BASE ÚNICA", header=0, dtype=str, engine="openpyxl")
        cursor = conn.cursor()
        
        for idx, r in df.iterrows():
            if idx == 0: continue 
            
            tipo_val = str(r.iloc[0]).strip().lower()
            if tipo_val != "insumo": continue 

            nome = str(r.get("Unnamed: 1", "")).strip()
            if not nome or nome.lower() == "nan": continue

            preco = _clean_price(r.get("Unnamed: 18"))
            if not (preco > 0): preco = 8.50

            # Insert Insumo
            cursor.execute('''
            INSERT OR REPLACE INTO insumos (id, nome, solubilidade, natureza_fisica, preco_unit, fornecedor)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (nome, nome, str(r.get("Unnamed: 7", "Média")), str(r.get("Unnamed: 8", "Sólida")), preco, str(r.get("Unnamed: 20", "N/A"))))

            # Parse and Insert Teores
            teor_raw = str(r.get("Unnamed: 6", ""))
            if teor_raw and teor_raw.lower() != "nan":
                teor_raw = teor_raw.replace(",", ".")
                parts = re.split(r'[;,\s]+', teor_raw)
                for p in parts:
                    if ":" in p:
                        try:
                            nut_name, val_s = p.split(":", 1)
                            nut_key = nut_name.strip().upper()
                            alias = {
                                "N": "N", "P": "P2O5", "P2O5": "P2O5", "K": "K2O", "K2O": "K2O", 
                                "CA": "Ca", "MG": "Mg", "S": "S", "SO4": "SO4", "B": "B", 
                                "ZN": "Zn", "CU": "Cu", "MN": "Mn", "MO": "Mo", "FE": "Fe", 
                                "CO": "Co", "NI": "Ni", "SE": "Se", "SI": "Si"
                            }
                            nut_key = alias.get(nut_key, nut_key)
                            val = _safe_float(val_s.strip())
                            if val > 0:
                                cursor.execute('INSERT OR REPLACE INTO teores (insumo_id, nutriente, valor) VALUES (?, ?, ?)', (nome, nut_key, val))
                        except Exception:
                            continue
        conn.commit()
    except Exception as e:
        print(f"Erro ao migrar insumos: {e}")

def migrate_aditivos(conn):
    print("Migrando Aditivos de COMPLETAO...")
    try:
        # header=None para usar iloc posicional
        df = pd.read_excel(EXCEL_PATH_COMPLETAO, sheet_name="Master (Tabela)", header=None, dtype=str, engine="openpyxl")
        cursor = conn.cursor()
        
        # Pula as duas primeiras linhas de cabeçalho
        for idx, r in df.iterrows():
            if idx < 2: continue
            
            nome = str(r.iloc[1]).strip()
            if not nome or nome.lower() == "nan": continue
            
            # Tenta pegar um preço padrão se não houver coluna de preço clara (ou usa 15.0 como padrão para aditivos)
            preco = 15.0 
            
            cursor.execute('''
            INSERT OR REPLACE INTO aditivos (id, nome, abreviatura, categoria, funcao, nutrientes_compativeis, ph_ideal, dose_legal, dose_tecnica, setup, alerta, observacoes, preco_unit)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (nome, nome, str(r.iloc[2]), str(r.iloc[0]), str(r.iloc[4]),
                  str(r.iloc[5]), str(r.iloc[6]), str(r.iloc[7]),
                  str(r.iloc[7]), str(r.iloc[8]), str(r.iloc[9]), str(r.iloc[10]), preco))
        conn.commit()
    except Exception as e:
        print(f"Erro ao migrar aditivos: {e}")

def migrate_processos(conn):
    print("Migrando Processos (POP/PCC) de COMPLETAO...")
    try:
        # SOR70_OPERACOES -> processos_pop
        df_op = pd.read_excel(EXCEL_PATH_COMPLETAO, sheet_name='SOR70_OPERACOES', header=1, dtype=str, engine='openpyxl')
        cursor = conn.cursor()
        for _, row in df_op.iterrows():
            etapa = str(row.iloc[0]).strip()
            if etapa != "nan":
                cursor.execute('INSERT INTO processos_pop (etapa, procedimento, notas) VALUES (?, ?, ?)',
                               (etapa, str(row.iloc[1]).strip(), str(row.iloc[2]).strip()))
        
        # SOR70_PCC -> processos_pcc
        df_pcc = pd.read_excel(EXCEL_PATH_COMPLETAO, sheet_name='SOR70_PCC', header=1, dtype=str, engine='openpyxl')
        for _, row in df_pcc.iterrows():
            pcc_id = str(row.iloc[0]).strip()
            if pcc_id != "nan":
                cursor.execute('INSERT OR REPLACE INTO processos_pcc (id, parametro, limite, acao) VALUES (?, ?, ?, ?)',
                               (pcc_id, str(row.iloc[1]).strip(), str(row.iloc[2]).strip(), str(row.iloc[3]).strip()))
        conn.commit()
    except Exception as e:
        print(f"Erro ao migrar processos: {e}")

def main() -> int:
    global BASE_DIR, EXCEL_PATH_BASE, EXCEL_PATH_COMPLETAO, DB_PATH

    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", default=str(BASE_DIR))
    ap.add_argument("--excel-base", default=str(EXCEL_PATH_BASE))
    ap.add_argument("--excel-completao", default=str(EXCEL_PATH_COMPLETAO))
    ap.add_argument("--db-path", default=str(DB_PATH))
    ap.add_argument("--import-aditivos-md", default="")
    args = ap.parse_args()

    BASE_DIR = Path(str(args.base_dir)).expanduser().resolve()
    EXCEL_PATH_BASE = Path(str(args.excel_base)).expanduser().resolve()
    EXCEL_PATH_COMPLETAO = Path(str(args.excel_completao)).expanduser().resolve()
    DB_PATH = Path(str(args.db_path)).expanduser().resolve()

    if str(args.import_aditivos_md or "").strip():
        md_path = Path(str(args.import_aditivos_md)).expanduser().resolve()
        conn = sqlite3.connect(DB_PATH)
        create_schema(conn)
        _ensure_aditivos_extra_columns(conn)
        n = import_aditivos_from_markdown(conn, md_path)
        conn.close()
        print(f"Aditivos importados do Markdown: {n} | DB: {DB_PATH}")
        return 0

    if not EXCEL_PATH_BASE.exists():
        print(f"Arquivo Excel BASE não encontrado em {EXCEL_PATH_BASE}")
        return 2
    if not EXCEL_PATH_COMPLETAO.exists():
        print(f"Arquivo Excel COMPLETAO não encontrado em {EXCEL_PATH_COMPLETAO}")
        return 2

    conn = sqlite3.connect(DB_PATH)
    create_schema(conn)
    _ensure_aditivos_extra_columns(conn)
    migrate_insumos(conn)
    migrate_aditivos(conn)
    migrate_processos(conn)
    conn.close()
    print(f"Banco de dados unificado criado e populado em: {DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
