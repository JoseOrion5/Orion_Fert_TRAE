import argparse
import os
import pandas as pd
import sqlite3
from pathlib import Path
import math
import re
import unicodedata

USD_BRL_RATE = 5.50
NUTRIENT_KEYS = ["N", "P2O5", "K2O", "Ca", "Mg", "SO4", "S", "B", "Zn", "Cu", "Mn", "Mo", "Fe", "Co", "Ni", "Se", "Si"]

def _norm_name(value: object) -> str:
    s = ("" if value is None else str(value)).strip().casefold()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _canonical_key(value: object) -> str:
    s = _norm_name(value)
    if not s:
        return ""
    s = re.sub(r"\(.*?\)", " ", s)
    s = s.replace("—", " ").replace("–", " ").replace("-", " ").replace(":", " ")
    s = re.sub(r"\s+", " ", s).strip()
    if s.startswith("ureia") and all(x not in s for x in ("superfosfato", "reline", "cloreto de colina", "formalde")):
        return "ureia"
    return s

def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        v = float(value)
        return v if math.isfinite(v) else None
    s = str(value).strip()
    if not s:
        return None
    s = s.replace("%", "").replace("R$", "").replace("US$", "").replace("U$", "").replace("USD", "").replace("BRL", "").replace("$", "").strip()
    s = s.replace(",", ".")
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

def _pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    cols = [str(c) for c in df.columns]
    cols_norm = {_norm_name(c): c for c in cols}
    for cand in candidates:
        c = cols_norm.get(_norm_name(cand))
        if c:
            return c
    for cand in candidates:
        cand_n = _norm_name(cand)
        for k, orig in cols_norm.items():
            if cand_n in k:
                return orig
    return None

def _parse_percent_value(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        v = float(value)
        return v if math.isfinite(v) else None
    s = str(value).strip()
    if not s:
        return None
    s = s.replace(",", ".")
    s = s.replace("—", "-").replace("–", "-")
    nums = re.findall(r"[-+]?\d+(?:\.\d+)?", s)
    if not nums:
        return None
    try:
        vals = [float(n) for n in nums[:2]]
    except ValueError:
        return None
    if len(vals) >= 2 and "-" in s:
        v = (vals[0] + vals[1]) / 2.0
    else:
        v = vals[0]
    return v if math.isfinite(v) else None

def _nutrient_key(label: str) -> str | None:
    s = _norm_name(label).replace("+", "")
    m = {
        "n": "N",
        "p2o5": "P2O5",
        "k2o": "K2O",
        "ca": "Ca",
        "mg": "Mg",
        "so4": "SO4",
        "s": "S",
        "b": "B",
        "zn": "Zn",
        "cu": "Cu",
        "mn": "Mn",
        "mo": "Mo",
        "fe": "Fe",
        "co": "Co",
        "ni": "Ni",
        "se": "Se",
        "si": "Si",
    }
    return m.get(s)

def _parse_nutrient_map(nutrientes_raw: object, teores_raw: object) -> dict[str, float]:
    nut_s = "" if nutrientes_raw is None else str(nutrientes_raw)
    teor_s = "" if teores_raw is None else str(teores_raw)
    out: dict[str, float] = {}

    pair_matches = re.findall(r"([A-Za-z0-9\+\-]{1,8})\s*[:=]\s*([^;,\n]+)", teor_s)
    for lab, vraw in pair_matches:
        k = _nutrient_key(lab)
        if not k:
            continue
        v = _parse_percent_value(vraw)
        if v is not None and v > 0:
            out[k] = v
    if out:
        return out

    nut_parts = [p.strip() for p in re.split(r"[;/,]+|/|\|", nut_s) if p and str(p).strip()]
    teor_parts = [p.strip() for p in re.split(r"[;/,]+|/|\|", teor_s) if p and str(p).strip()]
    if not nut_parts or not teor_parts:
        return {}
    if len(teor_parts) == 1 and len(nut_parts) >= 1:
        v = _parse_percent_value(teor_parts[0])
        if v is None or v <= 0:
            return {}
        for n in nut_parts:
            k = _nutrient_key(n)
            if k:
                out[k] = v
        return out
    if len(nut_parts) != len(teor_parts):
        return {}
    for n, t in zip(nut_parts, teor_parts):
        k = _nutrient_key(n)
        if not k:
            continue
        v = _parse_percent_value(t)
        if v is not None and v > 0:
            out[k] = v
    return out

def _extract_prices_from_simple_sheet(
    df: pd.DataFrame,
    *,
    source: str,
    default_currency: str | None = None,
) -> dict[str, list[tuple[str, float]]]:
    name_col = _pick_col(df, ["Insumo", "Nome", "Nome do Insumo", "Fertilizante", "Produto", "Item"])
    if not name_col:
        return {}

    price_col = _pick_col(df, ["Preço (R$/kg)", "Preço Médio (R$)", "Preço Médio (R$/kg)", "preco_medio_br", "Preço (R$)", "Preço"])
    currency_col = _pick_col(df, ["Moeda", "Moeda Original", "BRL", "Currency"])
    unit_col = _pick_col(df, ["Unidade", "unidade_preco", "unidade"])

    if not price_col:
        for c in df.columns:
            cn = _norm_name(c)
            if "preco" in cn or "preço" in cn:
                price_col = str(c)
                break

    if not price_col:
        return {}

    out: dict[str, list[tuple[str, float]]] = {}
    for _, row in df.iterrows():
        key = _canonical_key(row.get(name_col))
        if not key:
            continue
        v = _safe_float(row.get(price_col))
        if v is None or v <= 0 or not math.isfinite(v):
            continue

        currency = default_currency
        if currency_col:
            currency = ("" if row.get(currency_col) is None else str(row.get(currency_col))).strip().upper()
        if currency in {"USD", "U$", "US$"}:
            v = v * USD_BRL_RATE
        if unit_col:
            unit = ("" if row.get(unit_col) is None else str(row.get(unit_col))).strip().casefold()
            if unit in {"t", "ton", "tonelada", "toneladas"}:
                v = v / 1000.0
        if not (v > 0) or not math.isfinite(v):
            continue

        out.setdefault(key, []).append((source, float(v)))
    return out

def _load_prices_manus(manus_path: Path) -> dict[str, list[tuple[str, float]]]:
    if not manus_path.exists():
        return {}
    try:
        xls = pd.ExcelFile(manus_path)
    except Exception:
        return {}

    preferred = [s for s in xls.sheet_names if "preç" in _norm_name(s) or "preco" in _norm_name(s)]
    if not preferred:
        preferred = xls.sheet_names[:]

    merged: dict[str, list[tuple[str, float]]] = {}
    for sheet in preferred:
        try:
            df = pd.read_excel(xls, sheet_name=sheet)
        except Exception:
            continue
        m = _extract_prices_from_simple_sheet(df, source=f"Manus:{sheet}", default_currency="BRL")
        for k, vals in m.items():
            merged.setdefault(k, []).extend(vals)
    return merged

def _load_prices_claude(claude_path: Path) -> dict[str, list[tuple[str, float]]]:
    if not claude_path.exists():
        return {}
    try:
        xls = pd.ExcelFile(claude_path)
    except Exception:
        return {}

    merged: dict[str, list[tuple[str, float]]] = {}
    if "Fertilizantes (Catálogo)" in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name="Fertilizantes (Catálogo)")
            m = _extract_prices_from_simple_sheet(df, source="Claude:Fertilizantes (Catálogo)", default_currency="BRL")
            for k, vals in m.items():
                merged.setdefault(k, []).extend(vals)
        except Exception:
            pass

    for sheet in xls.sheet_names:
        sn = _norm_name(sheet)
        if "preç" not in sn and "preco" not in sn and "preco" not in sn and "market" not in sn:
            continue
        try:
            df = pd.read_excel(xls, sheet_name=sheet)
        except Exception:
            continue
        m = _extract_prices_from_simple_sheet(df, source=f"Claude:{sheet}", default_currency="BRL")
        for k, vals in m.items():
            merged.setdefault(k, []).extend(vals)
    return merged

def _load_prices_base_unique(df_base: pd.DataFrame) -> dict[str, list[tuple[str, float]]]:
    name_col = _pick_col(df_base, ["Nome", "Nome do Insumo", "Insumo"])
    price_brl_col = _pick_col(df_base, ["Estimativa de Preço Médio (R$)", "Preço Médio (R$)", "Preço (R$/kg)"])
    price_usd_col = _pick_col(df_base, ["Estimativa de Preço Médio (U$)", "Preço Médio (U$)", "Preço (U$/kg)"])
    currency_col = _pick_col(df_base, ["BRL", "Moeda", "Moeda Original", "Currency"])

    out: dict[str, list[tuple[str, float]]] = {}
    if not name_col:
        return out
    for _, row in df_base.iterrows():
        key = _canonical_key(row.get(name_col))
        if not key:
            continue
        v: float | None = None
        if price_brl_col:
            v = _safe_float(row.get(price_brl_col))
        if (v is None or v <= 0) and price_usd_col:
            vu = _safe_float(row.get(price_usd_col))
            if vu is not None and vu > 0:
                currency = ""
                if currency_col:
                    currency = ("" if row.get(currency_col) is None else str(row.get(currency_col))).strip().upper()
                if currency in {"BRL", "R$"}:
                    v = vu
                else:
                    v = vu * USD_BRL_RATE
        if v is None or v <= 0 or not math.isfinite(v):
            continue
        out.setdefault(key, []).append(("BaseÚnica", float(v)))
    return out

def _load_nutrients_claude_catalog(claude_path: Path) -> dict[str, dict[str, list[tuple[str, float]]]]:
    if not claude_path.exists():
        return {}
    try:
        df = pd.read_excel(claude_path, sheet_name="Fertilizantes (Catálogo)")
    except Exception:
        return {}

    name_col = _pick_col(df, ["nome", "Nome", "Insumo"])
    nut_col = _pick_col(df, ["nutriente", "Nutriente", "Nutriente(s)"])
    teor_col = _pick_col(df, ["teor_minimo_pct", "teor", "teor (%)", "Teor(es) / Garantia (%)"])
    out: dict[str, dict[str, list[tuple[str, float]]]] = {}
    if not (name_col and nut_col and teor_col):
        return out

    for _, row in df.iterrows():
        key = _canonical_key(row.get(name_col))
        if not key:
            continue
        nk = _nutrient_key(str(row.get(nut_col) or ""))
        if not nk:
            continue
        v = _parse_percent_value(row.get(teor_col))
        if v is None or v <= 0:
            continue
        out.setdefault(key, {}).setdefault(nk, []).append(("Claude:Fertilizantes (Catálogo)", float(v)))
    return out

def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    s = sum(values)
    return (s / len(values)) if math.isfinite(s) else None

def _merge_list_maps(maps: list[dict[str, list[tuple[str, float]]]]) -> dict[str, list[tuple[str, float]]]:
    out: dict[str, list[tuple[str, float]]] = {}
    for m in maps:
        for k, vals in m.items():
            out.setdefault(k, []).extend(vals)
    return out

def _default_base_dir() -> Path:
    env = (os.getenv("ORION_BASE_DIR") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parent


def create_unified_db(*, base_dir: Path | None = None):
    base_dir = (base_dir or _default_base_dir()).expanduser().resolve()
    completao_dir = base_dir / "COMPLETAO"

    excel_path = Path(os.getenv("ORION_EXCEL_BASE_UNICA") or (completao_dir / "BACKUP" / "2-BASE_UNICA_ATUALIZADA.xlsx"))
    manus_path = Path(os.getenv("ORION_EXCEL_MANUS") or (completao_dir / "Manus--COMPLETAO_COM_PRECOS.xlsx"))
    claude_path = Path(os.getenv("ORION_EXCEL_CLAUDE") or (completao_dir / "Claude-COMPLETAO_com_precos.xlsx"))
    db_path = Path(os.getenv("ORION_DB_PATH") or (base_dir / "orion_agroquim.db"))
    out_path = Path(os.getenv("ORION_OUT_XLSX") or (completao_dir / "DATABASE_MESTRE_ORION.xlsx"))

    with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
        print(f"Lendo {excel_path.name}...")
        if not excel_path.exists():
            print(f"Arquivo Excel não encontrado: {excel_path}")
            df_final = pd.DataFrame()
        else:
            df_base = pd.read_excel(excel_path)

            prices_by_key = _merge_list_maps([
                _load_prices_base_unique(df_base),
                _load_prices_claude(claude_path),
                _load_prices_manus(manus_path),
            ])
            for k, vals in list(prices_by_key.items()):
                seen: set[tuple[str, float]] = set()
                uniq: list[tuple[str, float]] = []
                for src, v in vals:
                    kk = (str(src), round(float(v), 6))
                    if kk in seen:
                        continue
                    seen.add(kk)
                    uniq.append((str(src), float(v)))
                prices_by_key[k] = uniq

            nutrients_by_key: dict[str, dict[str, list[tuple[str, float]]]] = {}
            base_meta: dict[str, dict[str, object]] = {}

            name_col = _pick_col(df_base, ["Nome", "Nome do Insumo", "Insumo"])
            tipo_col = _pick_col(df_base, ["Tipo"])
            cat_col = _pick_col(df_base, ["Categoria"])
            grupo_col = _pick_col(df_base, ["Grupo / Subtipo", "Grupo"])
            formula_col = _pick_col(df_base, ["Fórmula química", "Formula química", "formula_quimica"])
            sol_col = _pick_col(df_base, ["Solubilidade"])
            nat_col = _pick_col(df_base, ["Natureza física", "Natureza fisica", "natureza_fisica"])
            nut_raw_col = _pick_col(df_base, ["Nutriente(s)", "Nutrientes", "nutriente"])
            teor_raw_col = _pick_col(df_base, ["Teor(es) / Garantia (%)", "Garantia Nutricional", "teor"])

            for _, row in df_base.iterrows():
                if not name_col:
                    continue
                key = _canonical_key(row.get(name_col))
                if not key:
                    continue
                nm = "" if row.get(name_col) is None else str(row.get(name_col)).strip()
                base_meta.setdefault(key, {})["Nome"] = base_meta.get(key, {}).get("Nome") or nm
                if tipo_col:
                    base_meta[key]["Tipo"] = base_meta[key].get("Tipo") or row.get(tipo_col)
                if cat_col:
                    base_meta[key]["Categoria"] = base_meta[key].get("Categoria") or row.get(cat_col)
                if grupo_col:
                    base_meta[key]["Grupo / Subtipo"] = base_meta[key].get("Grupo / Subtipo") or row.get(grupo_col)
                if formula_col:
                    base_meta[key]["Fórmula química"] = base_meta[key].get("Fórmula química") or row.get(formula_col)
                if sol_col:
                    base_meta[key]["Solubilidade"] = base_meta[key].get("Solubilidade") or row.get(sol_col)
                if nat_col:
                    base_meta[key]["Natureza física"] = base_meta[key].get("Natureza física") or row.get(nat_col)

                nmap = _parse_nutrient_map(row.get(nut_raw_col) if nut_raw_col else None, row.get(teor_raw_col) if teor_raw_col else None)
                for nk, nv in nmap.items():
                    nutrients_by_key.setdefault(key, {}).setdefault(nk, []).append(("BaseÚnica", float(nv)))

            nutrients_claude = _load_nutrients_claude_catalog(claude_path)
            for key, d in nutrients_claude.items():
                for nk, vals in d.items():
                    nutrients_by_key.setdefault(key, {}).setdefault(nk, []).extend(vals)
            for k, d in list(nutrients_by_key.items()):
                for nk, vals in list(d.items()):
                    seen: set[tuple[str, float]] = set()
                    uniq: list[tuple[str, float]] = []
                    for src, v in vals:
                        kk = (str(src), round(float(v), 6))
                        if kk in seen:
                            continue
                        seen.add(kk)
                        uniq.append((str(src), float(v)))
                    nutrients_by_key[k][nk] = uniq

            rows_out: list[dict[str, object]] = []
            for key, d in nutrients_by_key.items():
                nm = (base_meta.get(key, {}) or {}).get("Nome") or key
                row_out: dict[str, object] = {
                    "Tipo": (base_meta.get(key, {}) or {}).get("Tipo") or "Insumo",
                    "Nome": nm,
                    "Categoria": (base_meta.get(key, {}) or {}).get("Categoria") or "",
                    "Grupo / Subtipo": (base_meta.get(key, {}) or {}).get("Grupo / Subtipo") or "",
                    "Fórmula química": (base_meta.get(key, {}) or {}).get("Fórmula química") or "",
                    "Solubilidade": (base_meta.get(key, {}) or {}).get("Solubilidade") or "",
                    "Natureza física": (base_meta.get(key, {}) or {}).get("Natureza física") or "",
                }

                any_nutrient = False
                for nk in NUTRIENT_KEYS:
                    vals = [v for _src, v in d.get(nk, []) if v is not None and v > 0]
                    mv = _mean(vals)
                    row_out[nk] = mv if (mv is not None and mv > 0) else ""
                    if mv is not None and mv > 0:
                        any_nutrient = True

                if not any_nutrient:
                    continue

                price_vals = prices_by_key.get(key, [])
                brl_vals = [v for _src, v in price_vals if v is not None and v > 0]
                price_mean = _mean(brl_vals)
                row_out["Estimativa de Preço Médio (R$)"] = round(price_mean, 4) if price_mean is not None else ""
                row_out["Estimativa de Preço Médio (U$)"] = round((price_mean / USD_BRL_RATE), 4) if price_mean is not None else ""
                row_out["BRL"] = "BRL" if price_mean is not None else ""
                row_out["Fonte/Fornecedor (preço)"] = "; ".join(sorted({src for src, _v in price_vals})) if price_vals else ""

                if len(brl_vals) > 1:
                    orig = ", ".join([f"{src}={round(v, 4)}" for src, v in price_vals])
                    print(f"MÉDIA PREÇO | {nm} | [{orig}] -> {round(price_mean or 0.0, 4)}")

                rows_out.append(row_out)

            df_final = pd.DataFrame(rows_out)
            if not df_final.empty:
                df_final = df_final.sort_values(by=["Nome"]).reset_index(drop=True)

        df_final.to_excel(writer, sheet_name="Insumos", index=False)
        print(f"-> Aba 'Insumos' adicionada com {len(df_final)} linhas.")

        print(f"\nLendo {db_path.name}...")
        if db_path.exists():
            conn = sqlite3.connect(db_path)
            
            try:
                df_aditivos = pd.read_sql_query("SELECT * FROM aditivos", conn)
                df_aditivos.to_excel(writer, sheet_name="Aditivos", index=False)
                print(f"-> Aba 'Aditivos' adicionada com {len(df_aditivos)} linhas.")
            except Exception as e:
                print(f"Erro ao ler Aditivos: {e}")
                
            try:
                df_pop = pd.read_sql_query("SELECT * FROM processos_pop", conn)
                df_pop.to_excel(writer, sheet_name="Processos_POP", index=False)
                print(f"-> Aba 'Processos_POP' adicionada com {len(df_pop)} linhas.")
            except Exception as e:
                print(f"Erro ao ler POP: {e}")
                
            try:
                df_pcc = pd.read_sql_query("SELECT * FROM processos_pcc", conn)
                df_pcc.to_excel(writer, sheet_name="Processos_PCC", index=False)
                print(f"-> Aba 'Processos_PCC' adicionada com {len(df_pcc)} linhas.")
            except Exception as e:
                print(f"Erro ao ler PCC: {e}")
                
            conn.close()
        else:
            print(f"Arquivo DB não encontrado: {db_path}")

    print(f"\nArquivo unificado criado com sucesso em:\n{out_path}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", default=str(_default_base_dir()))
    args = ap.parse_args()
    create_unified_db(base_dir=Path(str(args.base_dir)))
