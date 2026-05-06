import argparse
import math
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _norm_key(s: str) -> str:
    s = (s or "").strip().casefold()
    table = str.maketrans({"á": "a", "à": "a", "â": "a", "ã": "a", "ä": "a", "é": "e", "ê": "e", "ë": "e", "í": "i", "ï": "i", "ó": "o", "ô": "o", "õ": "o", "ö": "o", "ú": "u", "ü": "u", "ç": "c"})
    return s.translate(table)


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
    abbr = "".join([w[0].upper() for w in words[:6] if w and w[0].isalpha()])
    return abbr[:8]


def _overrides_from_name(name: str) -> Tuple[Optional[float], float, str]:
    k = _norm_key(name)
    if "xantana" in k:
        return None, 0.8, "Não-Newtoniano"
    if "attapulgita" in k or "atapulgita" in k or "bentonita" in k:
        return None, 999.0, "Não-Newtoniano"
    if "polissorbato 80" in k:
        return 15.0, 0.7, "Newtoniano"
    return None, 0.7, "Newtoniano"


def _ensure_columns(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
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
        """
    )
    conn.commit()

    cur.execute("PRAGMA table_info(aditivos)")
    cols = {str(r[1]) for r in (cur.fetchall() or [])}
    for name, ddl in [
        ("hlb", "ALTER TABLE aditivos ADD COLUMN hlb REAL"),
        ("limite_forca_ionica", "ALTER TABLE aditivos ADD COLUMN limite_forca_ionica REAL"),
        ("tipo_reologia", "ALTER TABLE aditivos ADD COLUMN tipo_reologia TEXT"),
    ]:
        if name not in cols:
            cur.execute(ddl)
    conn.commit()


def _read_base_geral_table(md_path: Path) -> List[Dict[str, str]]:
    lines = md_path.read_text(encoding="utf-8", errors="replace").splitlines()
    base_idx = next((i for i, ln in enumerate(lines) if ln.strip() == "## Base_Geral"), None)
    if base_idx is None:
        raise RuntimeError("Seção '## Base_Geral' não encontrada.")

    table_lines: List[str] = []
    for ln in lines[base_idx + 1:]:
        if ln.strip().startswith("|"):
            table_lines.append(ln.rstrip("\n"))
            continue
        if table_lines:
            break

    if len(table_lines) < 3:
        raise RuntimeError("Tabela de Base_Geral não encontrada ou vazia.")

    header = [c.strip() for c in table_lines[0].strip("|").split("|")]
    expected = ["Classe", "Aditivo", "Aplicação", "US$/kg_aprox", "US$/L_aprox", "Forma_típica", "Observações"]
    if [_norm_key(h) for h in header] != [_norm_key(w) for w in expected]:
        raise RuntimeError(f"Cabeçalho inesperado em Base_Geral. Esperado: {expected}. Encontrado: {header}.")

    out: List[Dict[str, str]] = []
    for ln in table_lines[2:]:
        parts = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(parts) < 7:
            continue
        if len(parts) > 7:
            parts = parts[:6] + [" | ".join(parts[6:]).strip()]
        row = dict(zip(expected, parts))
        if not str(row.get("Aditivo") or "").strip():
            continue
        out.append(row)
    return out


def import_aditivos_md(md_path: Path, db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        _ensure_columns(conn)
        rows = _read_base_geral_table(md_path)
        cur = conn.cursor()
        inserted = 0
        for r in rows:
            nome = str(r.get("Aditivo") or "").strip()
            grupo = str(r.get("Classe") or "").strip()
            funcao = str(r.get("Aplicação") or "").strip()
            setup = str(r.get("Forma_típica") or "").strip()
            obs = str(r.get("Observações") or "").strip()
            preco = _parse_price_range_to_float(r.get("US$/kg_aprox"))
            hlb, lim_i, rheo = _overrides_from_name(nome)
            cur.execute(
                """
                INSERT OR REPLACE INTO aditivos
                (id, nome, abreviatura, categoria, funcao, nutrientes_compativeis, ph_ideal, dose_legal, dose_tecnica, setup, alerta, observacoes, preco_unit, hlb, limite_forca_ionica, tipo_reologia)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    nome,
                    nome,
                    _abbr_from_name(nome),
                    grupo,
                    funcao,
                    "",
                    "",
                    "",
                    "",
                    setup,
                    "",
                    obs,
                    float(preco or 0.0),
                    hlb,
                    float(lim_i),
                    str(rheo),
                ),
            )
            inserted += 1
        conn.commit()
        return inserted
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", required=True)
    ap.add_argument("--db", required=True)
    args = ap.parse_args()

    md_path = Path(str(args.md)).expanduser().resolve()
    db_path = Path(str(args.db)).expanduser().resolve()
    if not md_path.exists():
        raise SystemExit(f"Arquivo .md não encontrado: {md_path}")
    db_path.parent.mkdir(parents=True, exist_ok=True)

    n = import_aditivos_md(md_path, db_path)
    print(f"Aditivos importados: {n} | DB: {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
