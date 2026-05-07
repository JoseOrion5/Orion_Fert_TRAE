import argparse
import os
import sqlite3
import pandas as pd
import re
import math
from pathlib import Path

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
        preco_unit REAL DEFAULT 0.0
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
    args = ap.parse_args()

    BASE_DIR = Path(str(args.base_dir)).expanduser().resolve()
    EXCEL_PATH_BASE = Path(str(args.excel_base)).expanduser().resolve()
    EXCEL_PATH_COMPLETAO = Path(str(args.excel_completao)).expanduser().resolve()
    DB_PATH = Path(str(args.db_path)).expanduser().resolve()

    if not EXCEL_PATH_BASE.exists():
        print(f"Arquivo Excel BASE não encontrado em {EXCEL_PATH_BASE}")
        return 2
    if not EXCEL_PATH_COMPLETAO.exists():
        print(f"Arquivo Excel COMPLETAO não encontrado em {EXCEL_PATH_COMPLETAO}")
        return 2

    conn = sqlite3.connect(DB_PATH)
    create_schema(conn)
    migrate_insumos(conn)
    migrate_aditivos(conn)
    migrate_processos(conn)
    conn.close()
    print(f"Banco de dados unificado criado e populado em: {DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
