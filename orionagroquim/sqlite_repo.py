from __future__ import annotations

from pathlib import Path
import math
import re
import sqlite3
import traceback
from typing import Any, Dict, List, Optional, Sequence, Tuple

from orionagroquim.config import DB_PATH, NUTRIENT_COLUMNS
from orionagroquim.models import Aditivo, Insumo


def _write_error_log(text: str) -> None:
    try:
        log_path = Path(__file__).resolve().parent.parent / "orionagroquim_error.log"
        log_path.write_text(text, encoding="utf-8", errors="replace")
    except Exception:
        pass


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip().replace("%", "").replace(",", ".")
    try:
        v = float(s)
        return v if math.isfinite(v) else None
    except ValueError:
        m = re.search(r"[-+]?\d*\.\d+|\d+", s)
        if not m:
            return None
        try:
            v = float(m.group())
            return v if math.isfinite(v) else None
        except ValueError:
            return None


def _norm_text(value: str) -> str:
    s = (value or "").strip().casefold()
    table = str.maketrans({"á": "a", "à": "a", "â": "a", "ã": "a", "ä": "a", "é": "e", "ê": "e", "ë": "e", "í": "i", "ï": "i", "ó": "o", "ô": "o", "õ": "o", "ö": "o", "ú": "u", "ü": "u", "ç": "c"})
    return s.translate(table)


def _nutrient_key_aliases() -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k_id, label in NUTRIENT_COLUMNS:
        out[_norm_text(k_id)] = k_id
        out[_norm_text(label)] = k_id
    out[_norm_text("CA+")] = "Ca"
    return out


def _sqlite_table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (table,))
    return cur.fetchone() is not None


def _load_insumos_from_sqlite() -> List[Insumo]:
    if not DB_PATH.exists():
        return []
    try:
        conn = sqlite3.connect(DB_PATH)
        if not _sqlite_table_exists(conn, "insumos") or not _sqlite_table_exists(conn, "teores"):
            conn.close()
            return []

        cur = conn.cursor()
        cur.execute("""
            SELECT
                i.id,
                i.nome,
                i.solubilidade,
                i.natureza_fisica,
                i.preco_unit,
                i.fornecedor,
                i.fator_v,
                i.rank_solubilidade,
                i.rank_custo,
                t.nutriente,
                t.valor
            FROM insumos i
            LEFT JOIN teores t ON t.insumo_id = i.id
            ORDER BY i.nome
        """)
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return []

        alias_map = _nutrient_key_aliases()
        by_id: Dict[str, Dict[str, Any]] = {}
        for (
            ins_id,
            nome,
            solub,
            natureza,
            preco_unit,
            fornecedor,
            fator_v,
            rank_sol,
            rank_custo,
            nutriente,
            valor,
        ) in rows:
            key = "" if ins_id is None else str(ins_id).strip()
            if not key:
                continue
            item = by_id.setdefault(key, {
                "id": key,
                "nome": "" if nome is None else str(nome).strip(),
                "solubilidade": "" if solub is None else str(solub).strip(),
                "natureza_fisica": "" if natureza is None else str(natureza).strip(),
                "preco_unit": float(preco_unit or 0.0),
                "fornecedor": "" if fornecedor is None else str(fornecedor).strip(),
                "fator_v": float(fator_v or 0.5),
                "rank_solubilidade": int(rank_sol or 3),
                "rank_custo": int(rank_custo or 3),
                "teores": {},
            })

            nut_raw = "" if nutriente is None else str(nutriente).strip()
            if not nut_raw:
                continue
            nk = alias_map.get(_norm_text(nut_raw))
            if not nk:
                continue
            v = _safe_float(valor)
            if v is None or v <= 0:
                continue
            item["teores"][nk] = float(v)

        insumos: List[Insumo] = []
        for item in by_id.values():
            teor_map = item.get("teores") or {}
            if not teor_map:
                continue

            rank_c = int(item.get("rank_custo") or 3)
            preco = float(item.get("preco_unit") or 0.0)
            if preco <= 0:
                fallback = {1: 3.50, 2: 5.50, 3: 8.50, 4: 12.50, 5: 18.00}
                preco = fallback.get(rank_c, 8.50)

            nm = str(item.get("nome") or "").strip()
            if not nm:
                nm = str(item.get("id") or "").strip()

            insumos.append(Insumo(
                id=str(item.get("id")),
                nome=nm,
                solubilidade=str(item.get("solubilidade") or "Média") or "Média",
                solubilidade_quente="",
                natureza_fisica=str(item.get("natureza_fisica") or "Sólida") or "Sólida",
                teor_por_nutriente_pct=dict(teor_map),
                rank_solubilidade=int(item.get("rank_solubilidade") or 3),
                rank_custo=rank_c,
                fator_v=float(item.get("fator_v") or 0.5),
                preco_unit=preco,
                fornecedor=str(item.get("fornecedor") or "N/A") or "N/A",
            ))
        return insumos
    except Exception as e:
        _write_error_log(f"Erro em _load_insumos_from_sqlite: {str(e)}\n{traceback.format_exc()}")
        return []


def load_insumos(use_pandas: bool = True, usd_brl_rate: float = 5.50) -> List[Insumo]:
    insumos_sql = _load_insumos_from_sqlite()
    if insumos_sql:
        return insumos_sql
    _write_error_log(
        "ERRO: SQLite é a fonte única de Insumos, mas não foi possível carregar dados.\n"
        f"- DB_PATH: {DB_PATH}\n"
        "Ação sugerida: popular as tabelas 'insumos' e 'teores' (ex.: via migrate_data.py) e tentar novamente.\n"
    )
    return []


def load_aditivos() -> List[Aditivo]:
    if not DB_PATH.exists():
        return []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(aditivos)")
        cols = {str(r[1]) for r in (cursor.fetchall() or [])}
        has_hlb = "hlb" in cols
        has_lim = "limite_forca_ionica" in cols
        has_rheo = "tipo_reologia" in cols

        sel = [
            "id",
            "nome",
            "abreviatura",
            "categoria",
            "funcao",
            "nutrientes_compativeis",
            "ph_ideal",
            "dose_legal",
            "dose_tecnica",
            "setup",
            "alerta",
            "observacoes",
            "preco_unit",
        ]
        if has_hlb:
            sel.append("hlb")
        if has_lim:
            sel.append("limite_forca_ionica")
        if has_rheo:
            sel.append("tipo_reologia")
        cursor.execute(f"SELECT {', '.join(sel)} FROM aditivos")
        rows = cursor.fetchall()

        aditivos: List[Aditivo] = []
        for r in rows:
            hlb = 0.0
            lim = 0.0
            rheo = ""
            if has_hlb:
                hlb = float(r[13] or 0.0)
            if has_lim:
                lim = float(r[14 if has_hlb else 13] or 0.0)
            if has_rheo:
                idx = 15 if (has_hlb and has_lim) else (14 if (has_hlb or has_lim) else 13)
                rheo = "" if r[idx] is None else str(r[idx])
            aditivos.append(Aditivo(
                id=r[0], nome=r[1], abreviatura=r[2], grupo=r[3], funcao_principal=r[4],
                nutrientes_compativeis=r[5], faixa_ph_ideal=r[6],
                dose_maxima_legal_pct=r[7], dose_maxima_tecnica_pct=r[8],
                modo_aplicacao=r[9], alerta_incompatibilidade=r[10],
                observacoes=r[11], preco_unit=r[12],
                hlb=hlb, limite_forca_ionica=lim, tipo_reologia=rheo
            ))
        conn.close()
        return aditivos
    except Exception as e:
        _write_error_log(f"Erro em load_aditivos (SQL): {str(e)}\n{traceback.format_exc()}")
        return []


def load_dados_seguranca() -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    if not DB_PATH.exists():
        return [], []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT etapa, procedimento, notas FROM processos_pop")
        pop_rows = cursor.fetchall()
        pop = [{"etapa": r[0], "procedimento": r[1], "notas": r[2]} for r in pop_rows]

        cursor.execute("SELECT id, parametro, limite, acao FROM processos_pcc")
        pcc_rows = cursor.fetchall()
        pcc = [{"id": r[0], "parametro": r[1], "limite": r[2], "acao": r[3]} for r in pcc_rows]

        conn.close()
        return pop, pcc
    except Exception as e:
        _write_error_log(f"Erro em load_dados_seguranca (SQL): {str(e)}\n{traceback.format_exc()}")
        return [], []
