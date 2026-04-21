from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import sys
import math
import re
import unicodedata
import traceback
import sqlite3
import numpy as np
from scipy.optimize import linprog
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

# --- CONFIGURAÇÃO DE DADOS CENTRALIZADA ---
COMPLETAO_DIR = Path(__file__).parent / "COMPLETAO"
COMPLETAO_XLSX = COMPLETAO_DIR / "COMPLETAO.xlsx"
BASE_UNICA_FILE = COMPLETAO_DIR / "DATABASE_MESTRE_ORION.xlsx"
DB_PATH = Path(__file__).parent / "orion_agroquim.db"  # Mantido para aditivos e segurança

DEFAULT_VOLUME_L = 100.0

NUTRIENT_COLUMNS: List[Tuple[str, str]] = [
    ("N", "N"), ("P2O5", "P2O5"), ("K2O", "K2O"), ("Ca", "Ca+"),
    ("Mg", "Mg"), ("SO4", "SO4"), ("S", "S"), ("B", "B"),
    ("Zn", "Zn"), ("Cu", "Cu"), ("Mn", "Mn"), ("Mo", "Mo"),
    ("Fe", "Fe"), ("Co", "Co"), ("Ni", "Ni"), ("Se", "Se"), ("Si", "Si"),
]

S_FROM_SO4_MASS_RATIO = 32.065 / 96.06

SOLUBILITY_NUTRIENT_PCT_CAPS: Dict[str, Dict[str, float]] = {
    "acido borico": {"B": 1.2},
    "ácido bórico": {"B": 1.2},
}

FAMILY_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "ureia": ("ureia", "uréia"),
    "nitrato_amonio": ("nitrato de amonio", "nitrato de amônio"),
    "acido_borico": ("acido borico", "ácido bórico"),
    "borato_sodio": (
        "borato de sodio", "borato de sódio",
        "tetraborato de sodio", "tetraborato de sódio",
        "borax", "bórax",
        "octaborato de sodio", "octaborato de sódio",
        "pentaborato de sodio", "pentaborato de sódio",
    ),
}

SPLIT_RULES: List[Dict[str, Any]] = [
    {"tier": 1, "nutrient": "N", "threshold_pct": 28.0, "min_family_shares": {"nitrato_amonio": 0.30, "ureia": 0.30}},
    {"tier": 1, "nutrient": "B", "threshold_pct": 1.5, "min_family_shares": {"acido_borico": 0.40, "borato_sodio": 0.40}},
]

KPS_ALERT_TEXT = "Risco de precipitação detectado: Requer complexação química"

KPS_PARES_PROIBIDOS: Dict[Tuple[str, str], Dict[str, Any]] = {
    ("Ca", "SO4"): {"risco": "Gesso (CaSO4)", "agente_quelante": "EDTA", "dose_pct": 0.05},
    ("Mg", "P2O5"): {"risco": "Fosfatos de magnésio", "agente_quelante": "EDTA", "dose_pct": 0.05},
}

def _kps_triggered_pairs(totals: Dict[str, float], targets: Optional[Dict[str, float]] = None) -> List[Tuple[str, str]]:
    def present(k: str) -> bool:
        return (totals.get(k, 0.0) or 0.0) > 0.0 or ((targets or {}).get(k, 0.0) or 0.0) > 0.0

    triggered: List[Tuple[str, str]] = []
    for (a, b), _meta in KPS_PARES_PROIBIDOS.items():
        if present(a) and present(b):
            triggered.append((a, b))
    return triggered

def _find_preferred_quelante(aditivos_cache: Sequence[Aditivo]) -> Optional[Aditivo]:
    preferred = ("EDTA", "HEDTA", "DTPA", "NTA")
    for abbr in preferred:
        hit = next((a for a in aditivos_cache if (a.abreviatura or "").strip().upper() == abbr), None)
        if hit:
            return hit

    def is_quelante(a: Aditivo) -> bool:
        return "quelant" in _norm_text(a.funcao_principal or "") or "quelant" in _norm_text(a.grupo or "")

    return next((a for a in aditivos_cache if is_quelante(a)), None)

def _lines_have_quelante(lines: Sequence[FormulaLine]) -> bool:
    for l in lines:
        nm = _norm_text(l.insumo_nome or "")
        if "edta" in nm or "hedta" in nm or "dtpa" in nm or "nta" in nm or "quelant" in nm:
            return True
    return False

def _name_has_any(name: str, keys: Sequence[str]) -> bool:
    nm = _norm_text(name)
    return any(_norm_text(k) in nm for k in keys if k)

def _insumo_is_family(ins: Insumo, family: str) -> bool:
    keys = FAMILY_KEYWORDS.get(family, ())
    return _name_has_any(ins.nome, keys)

BLOCKED_INSUMO_PATTERNS: List[str] = [
    "acetato", "alga marinha", "amonia anidra", "amônia anidra", "aquamonio", "aquamônio",
    "bicarbonato", "borato de monoetanolamina", "carbonato", "composto natural de folhelho carbonoso",
    "farinha de osso calcinado", "farinha de osso autoclavado", "formiato", "kieserita",
    "oxido", "óxido", "quelato", "termo fosfato magnesiano", "termofosfato magnesiano potassico",
    "termofosfato magnesiano potássico", "termo-superfosfato", "tetrapotassio difosfato",
    "tetrapotássio difosfato", "trioxido de molibdenio", "trióxido de molibdênio",
    "ureia-formaldeido", "uréia-formaldeído",
]

BLOCKED_OBS_LABELS: List[str] = [
    "Acetatos", "Alga marinha", "Amônia anidra", "Aquamônio", "Bicarbonatos",
    "Borato de Monoetanolamina", "Carbonatos em geral", "Composto natural de folhelho carbonoso",
    "Farinha de Osso Calcinado", "Farinha de Osso Autoclavado", "Formiatos em geral",
    "Kieserita", "Óxidos em geral", "Quelatos em geral", "Termo fosfato Magnesiano",
    "Termofosfato Magnesiano Potássico", "Termo-Superfosfato", "Tetrapotássio difosfato",
    "Trióxido de Molibdênio", "Uréia-Formaldeído",
]

@dataclass
class ThermoStatus:
    """Status Termodinâmico da Formulação"""
    agua_negativa: bool
    densidade_critica: bool
    agua_balanco_kg: float
    densidade_calculada: float
    is_supersaturado: bool
    tech_tier: int = 1  # 1: Base, 2: Avançada, 3: Experimental
    tech_instruction: str = ""

@dataclass(frozen=True)
class Insumo:
    id: str
    nome: str
    solubilidade: str
    natureza_fisica: str
    teor_por_nutriente_pct: Dict[str, float]
    rank_solubilidade: int
    rank_custo: int
    solubilidade_quente: str = ""
    fator_v: float = 0.5
    preco_unit: float = 0.0
    fornecedor: str = "N/A"
    lead_time: str = "N/A"
    is_local: bool = True
    local_origem: str = "N/A"

@dataclass(frozen=True)
class FormulaLine:
    insumo_nome: str
    massa_kg: float
    contrib_pct: Dict[str, float]
    preco_unit: float = 0.0
    custo_linha: float = 0.0
    fornecedor: str = "N/A"
    lead_time: str = "N/A"
    is_local: bool = True

@dataclass(frozen=True)
class Aditivo:
    id: str
    grupo: str
    nome: str
    abreviatura: str
    funcao_principal: str
    nutrientes_compativeis: str
    faixa_ph_ideal: str
    dose_maxima_legal_pct: str
    dose_maxima_tecnica_pct: str
    modo_aplicacao: str
    alerta_incompatibilidade: str
    observacoes: str
    preco_unit: float = 0.0

@dataclass(frozen=True)
class AditivoSuggestion:
    aditivo: Aditivo
    dose_recomendada_pct_texto: str
    dose_maxima_in39_pct_texto: str
    dose_recomendada_massa_texto: str
    motivo: str

@dataclass
class RelatorioOP:
    data_hora: str
    titulo: str
    bom_lines: List[FormulaLine]
    total_massa: float
    pop_etapas: List[Dict[str, str]]
    pcc_pontos: List[Dict[str, str]]
    tier: int
    densidade: float
    agua_balanco: float

# --- UTILITÁRIOS ---

def _norm_text(value: str) -> str:
    s = (value or "").strip().casefold()
    table = str.maketrans({"á": "a", "à": "a", "â": "a", "ã": "a", "ä": "a", "é": "e", "ê": "e", "ë": "e", "í": "i", "ï": "i", "ó": "o", "ô": "o", "õ": "o", "ö": "o", "ú": "u", "ü": "u", "ç": "c"})
    return s.translate(table)

def _canonical_key(value: str) -> str:
    s = _norm_text(value)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"\(.*?\)", " ", s)
    s = s.replace("—", " ").replace("–", " ").replace("-", " ").replace(":", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _safe_float(value: Any) -> Optional[float]:
    if value is None: return None
    s = str(value).strip().replace("%", "").replace(",", ".")
    try:
        v = float(s)
        return v if math.isfinite(v) else None
    except ValueError:
        m = re.search(r'[-+]?\d*\.\d+|\d+', s)
        if m:
            try:
                v = float(m.group())
                return v if math.isfinite(v) else None
            except ValueError:
                pass
        return None

def _safe_int(value: Any) -> Optional[int]:
    f = _safe_float(value)
    if f is None or not math.isfinite(f): return None
    try:
        return int(round(f))
    except (ValueError, OverflowError): return None

def _write_error_log(text: str) -> None:
    try:
        log_path = Path(__file__).resolve().parent / "orionagroquim_error.log"
        log_path.write_text(text, encoding="utf-8", errors="replace")
    except Exception:
        pass

def _clean_csv_header_name(value: Any) -> str:
    s = ("" if value is None else str(value)).strip()
    s = s.lstrip("\ufeff").strip()
    s = s.replace('""', '"').strip()
    if len(s) >= 2 and s.startswith('"') and s.endswith('"'):
        s = s[1:-1].strip()
    return s.strip()

def _clean_price(value: Any) -> float:
    if value is None: return 0.0
    s = str(value).strip().upper()
    if s in {"", "NAN", "NONE", "NULL", "-"}: return 0.0
    s = s.replace("US$", "").replace("USD", "").replace("R$", "").replace("$", "").replace("BRL", "").strip()
    s = s.replace(",", ".")
    try:
        v = float(s)
        return v if math.isfinite(v) else 0.0
    except ValueError: return 0.0

def _split_multi(value: str) -> List[str]:
    v = value.strip()
    if not v: return []
    v = v.replace(";", " ").strip()
    parts = [p.strip() for p in v.split("/") if p.strip()]
    return parts if len(parts) > 1 else [v]

def _parse_nutrientes_teores(nutriente_raw: Any, teor_raw: Any) -> Dict[str, float]:
    nutriente_s = ("" if nutriente_raw is None else str(nutriente_raw)).strip()
    teor_s = ("" if teor_raw is None else str(teor_raw)).strip()
    if not nutriente_s or not teor_s: return {}
    nutrientes = _split_multi(nutriente_s)
    teores_strs = _split_multi(teor_s)
    teores = [f for t in teores_strs if (f := _safe_float(t)) is not None]
    if not nutrientes or not teores: return {}
    if len(nutrientes) == 1 and len(teores) >= 1: return {nutrientes[0]: teores[0]}
    if len(nutrientes) != len(teores): return {n: teores[0] for n in nutrientes} if len(teores) == 1 else {}
    return {n: teores[i] for i, n in enumerate(nutrientes)}

def _is_blocked_insumo_name(name: str) -> bool:
    nm = _norm_text(name)
    return any(p in nm for p in BLOCKED_INSUMO_PATTERNS)

def format_num(value: Optional[float], digits: int = 4) -> str:
    if value is None or not math.isfinite(value): return "0.0000" if digits == 4 else "0.00"
    return f"{value:.{digits}f}"

def _effective_teor_pct(insumo: Insumo, nutrient: str) -> float:
    base = float(insumo.teor_por_nutriente_pct.get(nutrient, 0.0) or 0.0)
    if nutrient == "S" and base <= 0:
        so4 = float(insumo.teor_por_nutriente_pct.get("SO4", 0.0) or 0.0)
        if so4 > 0:
            return so4 * S_FROM_SO4_MASS_RATIO
    return base

def _contrib_pct_map(volume_l: float, massa_kg: float, insumo: Insumo) -> Dict[str, float]:
    out = {n: compute_contrib_percent(volume_l, massa_kg, t) for n, t in insumo.teor_por_nutriente_pct.items()}
    if ("S" not in out) or (out.get("S", 0.0) <= 0):
        so4 = float(insumo.teor_por_nutriente_pct.get("SO4", 0.0) or 0.0)
        if so4 > 0:
            out["S"] = out.get("S", 0.0) + compute_contrib_percent(volume_l, massa_kg, so4 * S_FROM_SO4_MASS_RATIO)
    return out

# --- CARREGAMENTO DE DADOS ---

def _extract_solubility_nutrient_caps(solubilidade: str) -> Dict[str, float]:
    s = (solubilidade or "").strip()
    if not s:
        return {}
    out: Dict[str, float] = {}
    for k, _ in NUTRIENT_COLUMNS:
        m = re.search(rf"(?i)\b{k}\b\s*[:=]?\s*(\d+(?:[\.,]\d+)?)\s*%", s)
        if not m:
            continue
        v = _safe_float(m.group(1))
        if v is not None and v > 0:
            out[k] = v
    m_b = re.search(r"(?i)(\d+(?:[\.,]\d+)?)\s*%\s*(boro|boron|b)\b", s)
    if m_b:
        v = _safe_float(m_b.group(1))
        if v is not None and v > 0:
            out.setdefault("B", v)
    return out

def _extract_solubility_mass_cap_kg(solubilidade: str, volume_l: float) -> Optional[float]:
    s = (solubilidade or "").strip()
    if not s or volume_l <= 0:
        return None
    sn = _norm_text(s)
    m = re.search(r"(?i)(\d+(?:[\.,]\d+)?)\s*g\s*/\s*l", s)
    if m:
        gpl = _safe_float(m.group(1))
        if gpl is not None and gpl > 0:
            return (gpl / 1000.0) * volume_l
    m = re.search(r"(?i)(\d+(?:[\.,]\d+)?)\s*g\s*/\s*100\s*ml", s)
    if m:
        g_100ml = _safe_float(m.group(1))
        if g_100ml is not None and g_100ml > 0:
            return (g_100ml * (volume_l * 10.0)) / 1000.0
    m = re.search(r"(?i)(\d+(?:[\.,]\d+)?)\s*kg\s*/\s*m3", s)
    if m:
        kgm3 = _safe_float(m.group(1))
        if kgm3 is not None and kgm3 > 0:
            return kgm3 * (volume_l / 1000.0)
    if "baixa" in sn and "suspens" in sn:
        return 0.25 * volume_l
    if "teor total" in sn:
        return 0.12 * volume_l
    return None

def _solubility_limit_mass_kg_from_text(solubilidade: str, volume_l: float) -> Optional[float]:
    cap = _extract_solubility_mass_cap_kg(solubilidade, volume_l)
    if cap is not None and cap > 0:
        return cap

    sn = _norm_text(solubilidade or "")
    if not sn or volume_l <= 0:
        return None

    if "misc" in sn or "totalmente" in sn:
        return None

    if ("muito alta" in sn) or ("muit" in sn and "alta" in sn) or ("alt" in sn and "solu" in sn):
        return 0.40 * volume_l
    if "alta" in sn:
        return 0.33 * volume_l
    if "media" in sn or "média" in sn:
        return 0.22 * volume_l
    if "baixa" in sn:
        return 0.12 * volume_l
    if "insolu" in sn or ("pouco" in sn and "solu" in sn):
        return 0.08 * volume_l

    return None

def _solubility_limit_mass_kg(insumo: Insumo, volume_l: float, *, use_hot_solubility: bool = False) -> Optional[float]:
    txt = insumo.solubilidade_quente if (use_hot_solubility and (insumo.solubilidade_quente or "").strip()) else insumo.solubilidade
    return _solubility_limit_mass_kg_from_text(txt, volume_l)

def _saturation_index_total(lines: Sequence[FormulaLine], insumos: Sequence[Insumo], volume_l: float, *, use_hot_solubility: bool = False) -> float:
    if volume_l <= 0:
        return 0.0
    by_name = {i.nome: i for i in insumos}
    total = 0.0
    for l in lines:
        ins = by_name.get(l.insumo_nome)
        if not ins:
            continue
        lim = _solubility_limit_mass_kg(ins, volume_l, use_hot_solubility=use_hot_solubility)
        if lim is None or lim <= 0:
            continue
        total += max(0.0, float(l.massa_kg)) / float(lim)
    return float(total)

def _cap_mass_by_saturation(
    insumo: Insumo,
    desired_mass_kg: float,
    current_lines: Sequence[FormulaLine],
    insumos: Sequence[Insumo],
    volume_l: float,
) -> float:
    if desired_mass_kg <= 0 or volume_l <= 0:
        return 0.0
    lim = _solubility_limit_mass_kg(insumo, volume_l)
    if lim is None or lim <= 0:
        return float(desired_mass_kg)
    before = _saturation_index_total(current_lines, insumos, volume_l)
    remaining = 1.0 - float(before)
    if remaining <= 0:
        return 0.0
    allowed = remaining * float(lim)
    return float(min(desired_mass_kg, allowed))

def _solubility_cap_mass_kg(insumo: Insumo, volume_l: float, targets: Dict[str, float], multiplier: float = 1.0) -> Optional[float]:
    if volume_l <= 0:
        return None
    base = _canonical_key(insumo.nome)
    caps: Dict[str, float] = {}
    for k, d in SOLUBILITY_NUTRIENT_PCT_CAPS.items():
        if k in base:
            for nk, nv in d.items():
                caps[nk] = max(caps.get(nk, 0.0), float(nv))
    for nk, nv in _extract_solubility_nutrient_caps(insumo.solubilidade).items():
        caps[nk] = max(caps.get(nk, 0.0), float(nv))

    mass_caps: List[float] = []
    mass_from_text = _extract_solubility_mass_cap_kg(insumo.solubilidade, volume_l)
    if mass_from_text is not None and mass_from_text > 0:
        mass_caps.append(mass_from_text)

    for nk, cap_pct in caps.items():
        if (targets.get(nk) or 0.0) <= 0:
            continue
        teor = insumo.teor_por_nutriente_pct.get(nk, 0.0)
        if teor <= 0:
            continue
        ub = (volume_l * cap_pct) / teor
        if ub > 0 and math.isfinite(ub):
            mass_caps.append(ub)
    if not mass_caps:
        return None
    return min(mass_caps) * multiplier

def load_insumos(use_pandas: bool = True, usd_brl_rate: float = 5.50) -> List[Insumo]:
    # Tenta ler a sua nova fonte de verdade consolidada
    if not BASE_UNICA_FILE.exists():
        _write_error_log(f"ERRO: Planilha unificada {BASE_UNICA_FILE} não encontrada.")
        return []
    
    try:
        import pandas as pd
        if BASE_UNICA_FILE.suffix.lower() == ".csv":
            df = pd.read_csv(BASE_UNICA_FILE, dtype=str, encoding="utf-8")
        else:
            df = pd.read_excel(BASE_UNICA_FILE, dtype=str, sheet_name="Insumos")
            
        df.columns = [_clean_csv_header_name(c).lower() for c in df.columns]
        rows = df.to_dict(orient="records")
        
        insumos = []
        for r in rows:
            nome = str(r.get("nome", r.get("insumo", r.get("nome do insumo", "")))).strip()
            if not nome or nome.lower() == "nan": continue
            
            # BUSCA OTIMIZADA: Tenta todas as formas possíveis de coluna de preço
            preco_brl = _clean_price(r.get("estimativa de preço médio (r$)") or r.get("preco_unitario") or r.get("preco base") or r.get("preço") or r.get("r$/kg"))
            preco_usd = _clean_price(r.get("estimativa de preço médio (u$)") or r.get("preco_usd") or r.get("preco_dolar") or r.get("us$/kg"))
            currency = str(r.get("brl", r.get("unnamed: 21", ""))).strip().upper()
            
            # Ajuste de moeda baseado no que fundimos
            preco = preco_brl
            if currency == "USD" and preco_usd > 0:
                preco = preco_usd * usd_brl_rate
            elif preco <= 0 and preco_usd > 0:
                preco = preco_usd * usd_brl_rate
            
            rank_s = int(_safe_float(r.get("rank_solubilidade", r.get("solubilidade"))) or 3)
            rank_c = int(_safe_float(r.get("rank_custo")) or 3)
            
            if preco <= 0:
                fallback = {1: 3.50, 2: 5.50, 3: 8.50, 4: 12.50, 5: 18.00}
                preco = fallback.get(rank_c, 8.50)

            teor_map = {}
            # Busca flexível por colunas de nutrientes diretas
            for k_id, label in NUTRIENT_COLUMNS:
                val = _safe_float(r.get(k_id.lower()) or r.get(label.lower()) or r.get(f"{label.lower()} (%)"))
                if val is not None and val > 0:
                    teor_map[k_id] = val

            # O excel consolidado aglutina num campo de 'Teor(es) / Garantia (%)' 
            # Vamos usar a função parse nativa para extrair os dados.
            if not teor_map:
                nut_str = str(r.get("nutriente(s)", ""))
                teor_str = str(r.get("teor(es) / garantia (%)", ""))
                parsed_teor = _parse_nutrientes_teores(nut_str, teor_str)
                for pk, pv in parsed_teor.items():
                    # Match case-insensitive com Nutrient Columns
                    found_k = next((nk for nk, nl in NUTRIENT_COLUMNS if nk.lower() == pk.lower() or nl.lower() == pk.lower()), None)
                    if found_k:
                        teor_map[found_k] = pv

            if not teor_map: continue
            
            insumos.append(Insumo(
                id=nome, nome=nome, 
                solubilidade=str(r.get("solubilidade", "Média")),
                solubilidade_quente=str(r.get("solubilidade_quente") or r.get("solubilidade quente") or r.get("solubilidade a quente") or r.get("solubilidade (quente)") or ""),
                natureza_fisica=str(r.get("natureza física", "Sólida")),
                teor_por_nutriente_pct=teor_map, rank_solubilidade=rank_s, rank_custo=rank_c,
                preco_unit=preco, fornecedor=str(r.get("fonte/fornecedor (preço)", "N/A"))
            ))
        return insumos
    except Exception as e:
        _write_error_log(f"Erro em load_insumos (Pandas): {str(e)}\n{traceback.format_exc()}")
        return []

def load_aditivos() -> List[Aditivo]:
    if not DB_PATH.exists(): return []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome, abreviatura, categoria, funcao, nutrientes_compativeis, ph_ideal, dose_legal, dose_tecnica, setup, alerta, observacoes, preco_unit FROM aditivos")
        rows = cursor.fetchall()
        
        aditivos = []
        for r in rows:
            aditivos.append(Aditivo(
                id=r[0], nome=r[1], abreviatura=r[2], grupo=r[3], funcao_principal=r[4],
                nutrientes_compativeis=r[5], faixa_ph_ideal=r[6],
                dose_maxima_legal_pct=r[7], dose_maxima_tecnica_pct=r[8], 
                modo_aplicacao=r[9], alerta_incompatibilidade=r[10], 
                observacoes=r[11], preco_unit=r[12]
            ))
        conn.close()
        return aditivos
    except Exception as e:
        _write_error_log(f"Erro em load_aditivos (SQL): {str(e)}\n{traceback.format_exc()}")
        return []

def load_dados_seguranca() -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """Lê dados de segurança e processos do banco de dados unificado"""
    if not DB_PATH.exists(): return [], []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # POP Operações
        cursor.execute("SELECT etapa, procedimento, notas FROM processos_pop")
        pop_rows = cursor.fetchall()
        pop = [{"etapa": r[0], "procedimento": r[1], "notas": r[2]} for r in pop_rows]
        
        # PCC Pontos Críticos
        cursor.execute("SELECT id, parametro, limite, acao FROM processos_pcc")
        pcc_rows = cursor.fetchall()
        pcc = [{"id": r[0], "parametro": r[1], "limite": r[2], "acao": r[3]} for r in pcc_rows]
        
        conn.close()
        return pop, pcc
    except Exception as e:
        _write_error_log(f"Erro em load_dados_seguranca (SQL): {str(e)}")
        return [], []

# --- CÁLCULOS E LÓGICA ---

def compute_mass_kg_for_target(volume_l: float, target_percent: float, teor_pct: float) -> Optional[float]:
    if volume_l <= 0 or target_percent <= 0 or teor_pct <= 0: return None
    return (volume_l * target_percent) / teor_pct

def compute_contrib_percent(volume_l: float, massa_kg: float, teor_pct: float) -> float:
    if volume_l <= 0: return 0.0
    return (massa_kg * teor_pct) / volume_l

def build_line_for_target(volume_l: float, insumo: Insumo, target_nutrient: str, target_percent: float) -> Optional[FormulaLine]:
    teor = _effective_teor_pct(insumo, target_nutrient)
    if teor <= 0: return None
    massa = compute_mass_kg_for_target(volume_l, target_percent, teor)
    if massa is None: return None
    contrib = _contrib_pct_map(volume_l, massa, insumo)
    return FormulaLine(insumo.nome, massa, contrib, insumo.preco_unit, massa * insumo.preco_unit, insumo.fornecedor, insumo.lead_time, insumo.is_local)

def merge_lines(lines: Sequence[FormulaLine]) -> List[FormulaLine]:
    by_name = {}
    for l in lines:
        if l.insumo_nome not in by_name:
            by_name[l.insumo_nome] = {"mass": 0.0, "contrib": {}, "p": l.preco_unit, "f": l.fornecedor, "lt": l.lead_time, "loc": l.is_local}
        d = by_name[l.insumo_nome]
        d["mass"] += l.massa_kg
        for n, v in l.contrib_pct.items(): d["contrib"][n] = d["contrib"].get(n, 0.0) + v
    
    return sorted([FormulaLine(n, d["mass"], d["contrib"], d["p"], d["mass"]*d["p"], d["f"], d["lt"], d["loc"]) for n, d in by_name.items()], key=lambda x: x.massa_kg, reverse=True)

def _estimated_density(lines: Sequence[FormulaLine], insumos: Sequence[Insumo], volume_l: float) -> Optional[float]:
    if volume_l <= 0: return None
    by_name = {i.nome: i for i in insumos}
    total_sais = sum(max(0.0, l.massa_kg) for l in lines)
    total_fv = 0.0
    massa_agua_em_liquidos = 0.0
    for l in lines:
        ins = by_name.get(l.insumo_nome)
        fv = float(ins.fator_v) if ins else 0.5
        m_kg = max(0.0, l.massa_kg)
        total_fv += m_kg * fv
        nm = _norm_text(l.insumo_nome)
        if "sorbitol" in nm or "glicerina" in nm: massa_agua_em_liquidos += m_kg * 0.30
        elif "acido fosforico" in nm: massa_agua_em_liquidos += m_kg * 0.15
    
    agua_livre = max(0.0, volume_l - massa_agua_em_liquidos)
    massa_total = agua_livre + massa_agua_em_liquidos + total_sais
    denom = agua_livre + total_fv
    return massa_total / denom if denom > 0 else None

def calcular_agua_qsp(volume_alvo_l: float, linhas_formula: Sequence[FormulaLine], insumos_bd: Sequence[Insumo]) -> float:
    by_name = {i.nome: i for i in insumos_bd}
    vol_sais = 0.0
    massa_agua = 0.0
    for l in linhas_formula:
        ins = by_name.get(l.insumo_nome)
        fv = float(ins.fator_v) if ins else 0.5
        m_kg = max(0.0, l.massa_kg)
        vol_sais += m_kg * fv
        nm = _norm_text(l.insumo_nome)
        if "sorbitol" in nm or "glicerina" in nm: massa_agua += m_kg * 0.30
        elif "acido fosforico" in nm: massa_agua += m_kg * 0.15
    return max(float(volume_alvo_l) - vol_sais - massa_agua, 0.0)

def verificar_viabilidade_termodinamica(volume_alvo_l: float, linhas_formula: Sequence[FormulaLine], insumos_bd: Sequence[Insumo], formula_index: int = 1) -> ThermoStatus:
    agua_balanco = calcular_agua_qsp(volume_alvo_l, linhas_formula, insumos_bd)
    densidade = _estimated_density(linhas_formula, insumos_bd, volume_alvo_l) or 1.0
    tier = 1 if 1 <= formula_index <= 4 else (2 if 5 <= formula_index <= 8 else 3)
    instr = "Soluções Verdadeiras / Frio" if tier == 1 else ("Permite Suspensão / Co-solventes Seguros" if tier == 2 else "Reator com Aquecimento e Alto Torque")
    return ThermoStatus(agua_balanco < 0, densidade > 1.45, agua_balanco, densidade, (agua_balanco < 0 or densidade > 1.45), tier, instr)

def calcular_custo_industrial(lines: Sequence[FormulaLine], volume_l: float, tech_tier: int, aditivos_cache: List[Aditivo]) -> float:
    total_custo = sum(l.custo_linha for l in lines)

    totals = _totals_from_lines(lines)
    triggered = _kps_triggered_pairs(totals)
    if triggered and volume_l > 0 and not _lines_have_quelante(lines):
        quelante = _find_preferred_quelante(aditivos_cache)
        if quelante and (quelante.preco_unit or 0.0) > 0:
            dose_pct = max(float(KPS_PARES_PROIBIDOS[p]["dose_pct"]) for p in triggered)
            massa_kg = (volume_l * dose_pct) / 100.0
            total_custo += massa_kg * float(quelante.preco_unit)

    if tech_tier == 3:
        sorbitol = next((a for a in aditivos_cache if _norm_text(a.abreviatura) == "sor-70"), None)
        if sorbitol: total_custo += (volume_l * 0.05 * sorbitol.preco_unit)
    return total_custo

def gerar_relatorio_op(lines: List[FormulaLine], volume_l: float, status: ThermoStatus) -> RelatorioOP:
    """Gera estrutura de dados para o Laudo Industrial"""
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    pop, pcc = [], []
    
    if status.tech_tier == 3:
        pop, pcc = load_dados_seguranca()
    else:
        # POP Padrão para Tier 1 e 2
        pop = [
            {"etapa": "1. Início", "procedimento": "Adicionar 70% da água QSP.", "notas": "Agitação média"},
            {"etapa": "2. Sais", "procedimento": "Adicionar sais por ordem de solubilidade.", "notas": "Evitar grumos"},
            {"etapa": "3. Final", "procedimento": "Completar volume e ajustar pH.", "notas": "Estabilização"}
        ]
        pcc = [{"id": "PCC-STD", "parametro": "pH e Densidade", "limite": "Conforme TDS", "acao": "Ajustar ou Rejeitar"}]

    nutrient_keys = [k for k, _ in NUTRIENT_COLUMNS]
    complex_nutrients: List[str] = []
    for k in nutrient_keys:
        sources = sum(1 for l in lines if (l.contrib_pct.get(k, 0.0) or 0.0) > 0.0)
        if sources > 2:
            complex_nutrients.append(k)
    title = f"ORDEM DE PRODUÇÃO - TIER {status.tech_tier}"
    if complex_nutrients:
        title = f"{title} | ALERTA: Mistura Complexa ({', '.join(complex_nutrients)})"

    return RelatorioOP(
        data_hora=now,
        titulo=title,
        bom_lines=lines,
        total_massa=sum(l.massa_kg for l in lines),
        pop_etapas=pop,
        pcc_pontos=pcc,
        tier=status.tech_tier,
        densidade=status.densidade_calculada,
        agua_balanco=status.agua_balanco_kg
    )

def recommend_process_and_aditivos(
    targets: Dict[str, float],
    lines: Sequence[FormulaLine],
    aditivos: Sequence[Aditivo],
    insumos: Sequence[Insumo],
    volume_l: float,
    temp_c: float,
    *,
    reactor_level_available: Optional[int] = None,
    experimental: bool = False,
    strategy_label: Optional[str] = None,
    extreme_adjuvants: bool = False,
) -> Tuple[List[str], List[AditivoSuggestion]]:
    totals = _totals_from_lines(lines)
    target_b = targets.get("B", 0.0)
    total_b = totals.get("B", 0.0)

    insumo_by_name = {i.nome: i for i in insumos}
    used_insumos = [insumo_by_name.get(l.insumo_nome) for l in lines]
    used_insumos = [i for i in used_insumos if i is not None]

    has_ureia = _contains_insumo(lines, "uréia") or _contains_insumo(lines, "ureia")
    has_map = _contains_insumo(lines, "fosfato monoamônico") or _contains_insumo(lines, "fosfato monoamonico") or _contains_insumo(lines, "map")
    has_dap = _contains_insumo(lines, "fosfato diamônico") or _contains_insumo(lines, "fosfato diamonico") or _contains_insumo(lines, "dap")
    has_acid_phos = _contains_insumo(lines, "ácido fosfórico") or _contains_insumo(lines, "acido fosforico")
    has_solid = any("sólid" in _norm_text(i.natureza_fisica) or "solid" in _norm_text(i.natureza_fisica) for i in used_insumos)

    has_ca = ("Ca" in targets and targets.get("Ca", 0.0) > 0) or totals.get("Ca", 0.0) > 0
    has_mg = ("Mg" in targets and targets.get("Mg", 0.0) > 0) or totals.get("Mg", 0.0) > 0
    has_p = ("P2O5" in targets and targets.get("P2O5", 0.0) > 0) or totals.get("P2O5", 0.0) > 0
    has_so4 = ("SO4" in targets and targets.get("SO4", 0.0) > 0) or totals.get("SO4", 0.0) > 0
    has_s = ("S" in targets and targets.get("S", 0.0) > 0) or totals.get("S", 0.0) > 0
    has_micros = any(
        (targets.get(n, 0.0) > 0) or (totals.get(n, 0.0) > 0)
        for n in ("Fe", "Zn", "Mn", "Cu", "Mo", "Co", "Ni")
    )
    total_sais_kg = sum(l.massa_kg for l in lines)
    alta_carga_sais = (volume_l > 0) and ((total_sais_kg / volume_l) >= 0.18)
    kps_pairs = _kps_triggered_pairs(totals, targets)
    has_kps_risk = bool(kps_pairs)

    # Nível de complexidade aproximado
    def calcular_complexidade() -> int:
        c = 1
        if alta_carga_sais: c += 3
        if has_solid: c += 2
        if has_ca and (has_p or has_so4): c += 4
        return min(10, c)

    lvl = calcular_complexidade()
    high_complexity = lvl > 7

    chosen: List[Aditivo] = []
    
    def add_if_found(a: Optional[Aditivo]) -> None:
        if a and not any(x.id == a.id for x in chosen):
            chosen.append(a)

    def dose_max_pct(a: Aditivo) -> float:
        src = a.dose_maxima_tecnica_pct if experimental else a.dose_maxima_legal_pct
        v = _safe_float(src)
        pct = 0.0 if v is None else max(0.0, v)
        if experimental and extreme_adjuvants and pct > 0:
            pct = pct * 1.5
        return pct

    def pick_best(predicate: Callable[[Aditivo], bool]) -> Optional[Aditivo]:
        matches = [a for a in aditivos if predicate(a)]
        if not matches: return None
        matches.sort(key=lambda a: (dose_max_pct(a), (a.nome or "").strip()), reverse=True)
        return matches[0]

    def contains_any(text: str, needles: Sequence[str]) -> bool:
        t = (text or "").strip().casefold()
        return any(n.casefold() in t for n in needles if n)

    selected_nbpt = pick_best(lambda a: contains_any(a.nome or "", ["NBPT"]) or contains_any(a.abreviatura or "", ["NBPT"]))
    selected_anti = pick_best(lambda a: contains_any(a.grupo or "", ["Anticristalizante", "Umectante"]))
    selected_quelante = pick_best(lambda a: contains_any(a.funcao_principal or "", ["Quelante"]) or (a.abreviatura or "").strip().upper() in {"EDTA", "HEDTA", "DTPA", "NTA"})
    selected_acid_phos = pick_best(lambda a: (a.nome or "").strip().casefold() in {"ácido fosfórico", "acido fosforico"} and contains_any(a.grupo or "", ["Acidificante"]))

    if has_ureia: add_if_found(selected_nbpt)
    if (target_b >= 1.5) or (total_b >= 1.5) or (high_complexity or alta_carga_sais or has_solid): add_if_found(selected_anti)
    if (has_ca or has_micros or has_kps_risk or (has_mg and has_p)) and (not _lines_have_quelante(lines)): add_if_found(selected_quelante)
    if has_map or has_dap: add_if_found(selected_acid_phos)

    chosen = chosen[:6]
    process: List[str] = []
    step = 1

    def add_step(counter: int, text: str) -> int:
        process.append(f"Passo {counter}: {text}")
        return counter + 1

    def add_step_aditivo(counter: int, a: Aditivo, funcao: str, *, dose_pct: Optional[float] = None) -> int:
        pct = dose_pct if (dose_pct is not None and dose_pct > 0) else dose_max_pct(a)
        if pct is None or pct <= 0 or volume_l <= 0:
            return add_step(counter, f"Adicionar {a.nome} (Função: {funcao}).")
        massa_kg = (volume_l * pct) / 100.0
        
        # Injetar o aditivo diretamente como uma linha (FormulaLine) na lista da receita
        aditivo_como_linha = FormulaLine(
            insumo_nome=f"{a.nome} ({a.abreviatura})" if a.abreviatura else a.nome,
            massa_kg=massa_kg,
            contrib_pct={},
            preco_unit=a.preco_unit,
            custo_linha=massa_kg * a.preco_unit,
            is_local=False,
            fornecedor="Aditivo"
        )
        # Hack para adicionar à lista imutável/tuple mutável ou lidar com o fato de lines ser Sequence
        if isinstance(lines, list):
            lines.append(aditivo_como_linha)
            
        return add_step(counter, f"Adicionar {format_num(massa_kg, 3)} kg de {a.nome} (Função: {funcao}; dose {format_num(pct, 2)}%).")

    required_reactor_level = 1 if lvl <= 3 else (2 if lvl <= 7 else 3)
    available_level = 3 if reactor_level_available is None else max(1, min(3, int(reactor_level_available)))
    selected_level = min(required_reactor_level, available_level)

    if selected_level == 1:
        setup = "Tanque simples de PEAD ou Fibra. Operação a frio."
    elif selected_level == 2:
        setup = "Tanque de aço inox com agitação mecânica (turbina/hélice)."
    else:
        setup = "Reator Encamisado com agitação de alto torque e controle térmico rigoroso."

    if available_level < required_reactor_level:
        process.append(
            f"Passo 0: ALERTA - Formula exige SETUP nível {required_reactor_level}, mas o disponível é nível {available_level}. Ajustar estratégia/receita ou aceitar maior risco de instabilidade."
        )
    if has_kps_risk:
        process.append(f"Passo 0: ALERTA - {KPS_ALERT_TEXT}")
    process.append(f"Passo 0: SETUP - {setup}")

    agua_total = calcular_agua_qsp(volume_l, lines, insumos)
    v_inicial = agua_total * 0.70
    step = add_step(step, f"Adicionar {format_num(v_inicial, 1)} L de água (70% da água livre).")

    for a in chosen:
        step = add_step_aditivo(step, a, a.funcao_principal or a.grupo or "Aditivo")

    step = add_step(step, "Adicionar os sais em ordem de solubilidade (rank 1 -> 5).")
    step = add_step(step, f"Completar com {format_num(agua_total - v_inicial, 1)} L de água (Q.S.P final).")

    suggestions = []
    for a in chosen:
        used_pct = dose_max_pct(a)
        mass_val = (volume_l * used_pct) / 100.0 if (volume_l > 0 and used_pct > 0) else 0.0
        legal_pct = _safe_float(a.dose_maxima_legal_pct) or 0.0
        suggestions.append(AditivoSuggestion(a, f"{used_pct:.2f}%", f"{legal_pct:.2f}%", f"{mass_val:.3f} kg", "Recomendado para estabilidade"))

    return process, suggestions

def _totals_from_lines(lines: Sequence[FormulaLine]) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    for line in lines:
        for n, v in line.contrib_pct.items():
            totals[n] = totals.get(n, 0.0) + v
    return totals

def _contains_insumo(lines: Sequence[FormulaLine], contains_text: str) -> bool:
    t = contains_text.lower()
    return any(t in (l.insumo_nome or "").lower() for l in lines)

def _keyword_rank(text: str, keywords: Sequence[str]) -> int:
    t = _norm_text(text)
    for idx, k in enumerate(keywords):
        if _norm_text(k) in t: return idx
    return 10_000

def _apply_contrib_to_remaining(remaining: Dict[str, float], contrib: Dict[str, float]) -> Dict[str, float]:
    out = dict(remaining)
    for n, v in contrib.items():
        if n in out: out[n] = out.get(n, 0.0) - v
    return out

def _build_line_for_remaining(volume_l: float, insumo: Insumo, nutrient: str, remaining: Dict[str, float]) -> Optional[FormulaLine]:
    needed = remaining.get(nutrient, 0.0)
    if needed is None or needed <= 0: return None
    return build_line_for_target(volume_l, insumo, nutrient, needed)

def _build_np_combo_lines(volume_l: float, remaining: Dict[str, float], insumos: Sequence[Insumo], form_idx: int, is_compatible_fn: Optional[Callable[[Insumo], bool]] = None, commodity_rank_fn: Optional[Callable[[Insumo], int]] = None) -> List[FormulaLine]:
    target_n = remaining.get("N", 0.0)
    target_p = remaining.get("P2O5", 0.0)
    if target_n <= 0 or target_p <= 0: return []
    def check(i: Insumo) -> bool:
        if _is_blocked_insumo_name(i.nome): return False
        if is_compatible_fn and not is_compatible_fn(i): return False
        return True
    def c_rank(i: Insumo) -> int:
        if commodity_rank_fn: return commodity_rank_fn(i)
        return 0
    np_sources = [i for i in insumos if ("N" in i.teor_por_nutriente_pct and "P2O5" in i.teor_por_nutriente_pct and check(i))]
    if not np_sources: return []
    np_prefer = ["map", "dap", "fosfato"]
    np_sources.sort(key=lambda x: (c_rank(x), _keyword_rank(x.nome, np_prefer), -float(x.teor_por_nutriente_pct.get("P2O5", 0.0))))
    best_ins = np_sources[min(form_idx, len(np_sources)-1)]
    l = build_line_for_target(volume_l, best_ins, "P2O5", target_p)
    return [l] if l else []

def candidates_for(insumos: Sequence[Insumo], nutrient: str) -> List[Insumo]:
    cands = [i for i in insumos if (_effective_teor_pct(i, nutrient) > 0) and not _is_blocked_insumo_name(i.nome)]
    cands.sort(
        key=lambda x: (
            x.rank_solubilidade,
            -_effective_teor_pct(x, nutrient),
        )
    )
    return cands

def build_top12_forms(volume_l: float, targets: Dict[str, float], insumos: Sequence[Insumo], use_optimization: bool = False) -> List[List[FormulaLine]]:
    if use_optimization:
        optimized = _build_optimized_forms(volume_l, targets, insumos)
        heuristic = build_top12_forms(volume_l, targets, insumos, use_optimization=False)
        # Combina: se a otimizada falhou para um slot, usa a heurística
        for i in range(12):
            if not optimized[i]:
                optimized[i] = heuristic[i]
        return optimized
    
    forms: List[List[FormulaLine]] = []
    COMMODITIES = ["ureia", "uréia", "map", "cloreto", "sulfato", "nitrato", "acido borico", "ácido bórico"]
    def commodity_rank(ins: Insumo) -> int:
        nm = _norm_text(ins.nome)
        return 0 if any(c in nm for c in COMMODITIES) else 1
    
    for idx in range(12):
        tier = 1 if idx < 4 else (2 if idx < 8 else 3)
        multiplier = 1.0 if tier == 1 else (1.5 if tier == 2 else 100.0)
        
        remaining = dict(targets)
        lines: List[FormulaLine] = []
        def is_compatible(ins: Insumo) -> bool:
            return True
        def update_comp(ins: Insumo):
            return

        def _line_is_family(line: FormulaLine, family: str) -> bool:
            keys = FAMILY_KEYWORDS.get(family, ())
            return _name_has_any(line.insumo_nome or "", keys)

        def _family_contrib_pct(lines_seq: Sequence[FormulaLine], nutrient: str, family: str) -> float:
            return sum((l.contrib_pct.get(nutrient, 0.0) or 0.0) for l in lines_seq if _line_is_family(l, family))

        def _try_add_family_target_pct(nutrient: str, family: str, target_pct: float) -> None:
            nonlocal remaining, lines
            need_pct = remaining.get(nutrient, 0.0) or 0.0
            if need_pct <= 0 or target_pct <= 0:
                return
            target_pct = min(float(target_pct), float(need_pct))
            cands = [i for i in insumos if (nutrient in i.teor_por_nutriente_pct) and not _is_blocked_insumo_name(i.nome) and is_compatible(i) and _insumo_is_family(i, family)]
            cands.sort(key=lambda x: (commodity_rank(x), x.rank_solubilidade, -x.teor_por_nutriente_pct.get(nutrient, 0.0)))
            for pick in cands:
                teor = pick.teor_por_nutriente_pct.get(nutrient, 0.0) or 0.0
                if teor <= 0:
                    continue
                mass_need = compute_mass_kg_for_target(volume_l, target_pct, teor)
                if mass_need is None or mass_need <= 0:
                    continue
                ub = _solubility_cap_mass_kg(pick, volume_l, targets, multiplier)
                mass = float(mass_need)
                if ub is not None and ub > 0 and mass > ub:
                    mass = float(ub)
                mass = _cap_mass_by_saturation(pick, mass, lines, insumos, volume_l)
                if mass <= 0:
                    continue
                contrib = _contrib_pct_map(volume_l, mass, pick)
                lines.append(FormulaLine(pick.nome, mass, contrib, pick.preco_unit, mass * pick.preco_unit, pick.fornecedor, pick.lead_time, pick.is_local))
                remaining = _apply_contrib_to_remaining(remaining, contrib)
                update_comp(pick)
                return

        if remaining.get("N", 0.0) > 0 and remaining.get("P2O5", 0.0) > 0:
            np_lines = _build_np_combo_lines(volume_l, remaining, insumos, idx, is_compatible, commodity_rank)
            for l in np_lines:
                found = next((i for i in insumos if i.nome == l.insumo_nome), None)
                if found:
                    capped_mass = _cap_mass_by_saturation(found, float(l.massa_kg), lines, insumos, volume_l)
                    if capped_mass <= 0:
                        continue
                    if capped_mass + 1e-9 < float(l.massa_kg):
                        contrib = _contrib_pct_map(volume_l, capped_mass, found)
                        l = FormulaLine(found.nome, capped_mass, contrib, found.preco_unit, capped_mass * found.preco_unit, found.fornecedor, found.lead_time, found.is_local)
                lines.append(l)
                remaining = _apply_contrib_to_remaining(remaining, l.contrib_pct)
                if found:
                    update_comp(found)

        if tier == 1:
            for rule in SPLIT_RULES:
                if int(rule.get("tier", 0)) != tier:
                    continue
                nutrient = str(rule.get("nutrient", "")).strip()
                if not nutrient:
                    continue
                threshold = float(rule.get("threshold_pct", 0.0) or 0.0)
                target_pct_total = float(targets.get(nutrient, 0.0) or 0.0)
                if target_pct_total < threshold or target_pct_total <= 0:
                    continue
                min_family_shares = rule.get("min_family_shares") or {}
                if not isinstance(min_family_shares, dict):
                    continue
                for fam, share in min_family_shares.items():
                    fam_name = str(fam).strip()
                    min_share = float(share or 0.0)
                    if not fam_name or min_share <= 0:
                        continue
                    already = _family_contrib_pct(lines, nutrient, fam_name)
                    required = (target_pct_total * min_share) - already
                    if required > 1e-9:
                        _try_add_family_target_pct(nutrient, fam_name, required)

        for n, _ in NUTRIENT_COLUMNS:
            if remaining.get(n, 0.0) is None or remaining.get(n, 0.0) <= 0: continue
            sat_idx = _saturation_index_total(lines, insumos, volume_l)
            cands = []
            for i in insumos:
                if _is_blocked_insumo_name(i.nome) or not is_compatible(i):
                    continue
                teor = _effective_teor_pct(i, n)
                if teor <= 0:
                    continue
                mass_need = compute_mass_kg_for_target(volume_l, remaining.get(n, 0.0) or 0.0, teor)
                if mass_need is None or mass_need <= 0:
                    continue
                ub = _solubility_cap_mass_kg(i, volume_l, targets, multiplier)
                if ub is not None and ub > 0:
                    used_mass = sum(l.massa_kg for l in lines if l.insumo_nome == i.nome)
                    if (used_mass + float(mass_need)) > float(ub) + 1e-9:
                        continue
                lim = _solubility_limit_mass_kg(i, volume_l)
                if lim is not None and lim > 0:
                    if float(sat_idx) + (float(mass_need) / float(lim)) > 1.0 + 1e-9:
                        continue
                cands.append(i)
            cands.sort(key=lambda x: (commodity_rank(x), x.rank_solubilidade, -_effective_teor_pct(x, n)))
            if not cands: continue
            pick = cands[min(idx, len(cands)-1)]
            l = _build_line_for_remaining(volume_l, pick, n, remaining)
            if l:
                capped_mass = _cap_mass_by_saturation(pick, float(l.massa_kg), lines, insumos, volume_l)
                if capped_mass > 0:
                    if capped_mass + 1e-9 < float(l.massa_kg):
                        contrib = _contrib_pct_map(volume_l, capped_mass, pick)
                        l = FormulaLine(pick.nome, capped_mass, contrib, pick.preco_unit, capped_mass * pick.preco_unit, pick.fornecedor, pick.lead_time, pick.is_local)
                    lines.append(l)
                    remaining = _apply_contrib_to_remaining(remaining, l.contrib_pct)
                    update_comp(pick)
        final_lines = merge_lines(lines)
        totals = _totals_from_lines(final_lines)
        ok = True
        for k, t in targets.items():
            tv = float(t or 0.0)
            if tv <= 0:
                continue
            if float(totals.get(k, 0.0) or 0.0) + 1e-6 < tv:
                ok = False
                break
        if not ok:
            final_lines = []
        forms.append(final_lines)
        
        if final_lines and tier == 2:
            massa_glicerina = volume_l * 0.02
            forms[-1].append(FormulaLine(
                insumo_nome="Glicerina (Co-solvente)",
                massa_kg=massa_glicerina,
                contrib_pct={},
                preco_unit=4.00,
                custo_linha=massa_glicerina * 4.00,
                is_local=False
            ))
        elif final_lines and tier == 3:
            massa_sorbitol = volume_l * 0.05
            forms[-1].append(FormulaLine(
                insumo_nome="Sorbitol 70% (Co-solvente)",
                massa_kg=massa_sorbitol,
                contrib_pct={},
                preco_unit=5.00,
                custo_linha=massa_sorbitol * 5.00,
                is_local=False
            ))
            
    return forms

@dataclass(frozen=True)
class FormulaOutput:
    lines: List[FormulaLine]
    process_steps: List[str]
    aditivos_sugeridos: List[AditivoSuggestion]
    instrucoes_producao: List[str]
    aditivos: List[Dict[str, float]]
    indice_saturacao: float

def diagnosticar_operacoes_unitarias(
    lines: Sequence[FormulaLine],
    insumos: Sequence[Insumo],
    aditivos_sugeridos: Sequence[AditivoSuggestion],
    volume_l: float,
    temp_c: float,
) -> List[str]:
    sat = _saturation_index_total(lines, insumos, volume_l)

    def has_suspensor() -> bool:
        for s in aditivos_sugeridos:
            a = s.aditivo
            if "susp" in _norm_text(a.grupo or "") or "susp" in _norm_text(a.funcao_principal or ""):
                return True
        return any("susp" in _norm_text(l.insumo_nome or "") for l in lines)

    if sat < 0.6:
        regime = "Agitação Laminar (Simples)"
    elif (sat > 0.8) or has_suspensor():
        regime = "Agitação Turbulenta/High Shear"
    else:
        regime = "Agitação Moderada"

    nm_lines = [(_norm_text(l.insumo_nome or ""), float(l.massa_kg)) for l in lines]
    ureia_kg = sum(m for n, m in nm_lines if "ureia" in n or "uréia" in n)
    borico_kg = sum(m for n, m in nm_lines if "acido borico" in n or "ácido bórico" in n or ("boric" in n and "acid" in n))

    needs_heat = (volume_l > 0) and ((ureia_kg / volume_l) >= 0.12 or (borico_kg / volume_l) >= 0.04)

    def has_strong_acid() -> bool:
        acids = ("acido fosforico", "ácido fosfórico", "acido sulfurico", "ácido sulfúrico", "acido nitrico", "ácido nítrico")
        return any(a in (l.insumo_nome or "").casefold() for a in acids for l in lines)

    instr: List[str] = []
    instr.append(f"Regime de Agitação: {regime} (índice de saturação={format_num(sat, 3)}; T={format_num(temp_c, 1)}°C).")

    if needs_heat:
        sat_hot = _saturation_index_total(lines, insumos, volume_l, use_hot_solubility=True)
        instr.append(f"Perfil Térmico: Aquecimento a 60°C (carga endotérmica de ureia/ácido bórico). Considerar solubilidade_quente (índice a 60°C={format_num(sat_hot, 3)}).")

    if has_strong_acid():
        instr.append("Perfil Térmico: Adição Lenta com monitoramento de temperatura (reação exotérmica por ácidos).")

    by_name = {i.nome: i for i in insumos}
    stage2: List[FormulaLine] = []
    stage3: List[FormulaLine] = []
    stage4: List[FormulaLine] = []

    micros = {"B", "Zn", "Cu", "Mn", "Mo", "Fe", "Co", "Ni", "Se"}

    def is_stage2(l: FormulaLine) -> bool:
        if _norm_text(l.fornecedor or "") == "aditivo":
            return True
        nm = _norm_text(l.insumo_nome or "")
        return ("co solvente" in nm) or ("edta" in nm) or ("quelant" in nm) or ("umect" in nm) or ("anticrist" in nm)

    def is_micro(l: FormulaLine) -> bool:
        if any((l.contrib_pct.get(k, 0.0) or 0.0) > 0 for k in micros):
            return True
        nm = _norm_text(l.insumo_nome or "")
        return "micro" in nm and "nutr" in nm

    for l in lines:
        if is_stage2(l):
            stage2.append(l)
        elif is_micro(l):
            stage3.append(l)
        else:
            stage4.append(l)

    def sort_rank(ls: List[FormulaLine]) -> List[FormulaLine]:
        def rk(l: FormulaLine) -> int:
            ins = by_name.get(l.insumo_nome)
            return int(ins.rank_solubilidade) if ins else 3
        return sorted(ls, key=rk, reverse=True)

    stage3 = sort_rank(stage3)
    stage4 = sort_rank(stage4)

    def list_names(ls: Sequence[FormulaLine]) -> str:
        return ", ".join(f"{l.insumo_nome} ({format_num(float(l.massa_kg), 3)} kg)" for l in ls) if ls else "-"

    instr.append("Sequência de Adição Inteligente:")
    instr.append("1) Água (Q.S.P).")
    instr.append(f"2) Aditivos, quelantes e condicionadores: {list_names(stage2)}.")
    instr.append(f"3) Micronutrientes: {list_names(stage3)}.")
    instr.append(f"4) Insumos de Massa (N/Potássio e demais sais principais): {list_names(stage4)}.")
    return instr

def build_top12_outputs(
    volume_l: float,
    targets: Dict[str, float],
    insumos: Sequence[Insumo],
    aditivos: Sequence[Aditivo],
    temp_c: float,
    *,
    use_optimization: bool = False,
    reactor_level_available: Optional[int] = None,
    limite_diversificacao: float = 75.0,
) -> List[FormulaOutput]:
    if use_optimization:
        forms = _build_optimized_forms(volume_l, targets, insumos, aditivos=aditivos, limite_diversificacao=limite_diversificacao)
        heuristic = build_top12_forms(volume_l, targets, insumos, use_optimization=False)
        for i in range(12):
            if not forms[i]:
                forms[i] = heuristic[i]
    else:
        forms = build_top12_forms(volume_l, targets, insumos, use_optimization=False)
    outputs: List[FormulaOutput] = []
    for idx, base_lines in enumerate(forms, start=1):
        if not base_lines:
            outputs.append(FormulaOutput([], [], [], [], [], 0.0))
            continue
        lines = list(base_lines)
        steps, ad_sug = recommend_process_and_aditivos(
            targets,
            lines,
            aditivos,
            insumos,
            volume_l,
            temp_c,
            reactor_level_available=reactor_level_available,
        )
        instrucoes = diagnosticar_operacoes_unitarias(lines, insumos, ad_sug, volume_l, temp_c)
        aditivos_usados: List[Dict[str, float]] = []
        for l in lines:
            if _norm_text(l.fornecedor or "") == "aditivo":
                aditivos_usados.append({"nome": str(l.insumo_nome or ""), "massa_kg": float(l.massa_kg)})
        sat = _saturation_index_total(lines, insumos, volume_l)
        outputs.append(FormulaOutput(lines, steps, ad_sug, instrucoes, aditivos_usados, sat))
    return outputs

def _build_optimized_forms(
    volume_l: float,
    targets: Dict[str, float],
    insumos: Sequence[Insumo],
    aditivos: Sequence[Aditivo] = (),
    *,
    limite_diversificacao: float = 75.0,
) -> List[List[FormulaLine]]:
    """Motor de Otimização Simplex para combinar múltiplos insumos com menor custo"""
    # Filtra insumos úteis e não bloqueados
    valid_insumos = [i for i in insumos if not _is_blocked_insumo_name(i.nome)]
    if not valid_insumos: return [[] for _ in range(12)]

    limite_diversificacao = float(limite_diversificacao or 0.0)
    limite_diversificacao = max(50.0, min(100.0, limite_diversificacao))
    cap_share = limite_diversificacao / 100.0

    forced_quelante_idx: Optional[int] = None
    forced_quelante_lb_kg = 0.0
    if (targets.get("Ca", 0.0) or 0.0) > 0 and ((targets.get("S", 0.0) or 0.0) > 0 or (targets.get("SO4", 0.0) or 0.0) > 0):
        q = _find_preferred_quelante(aditivos)
        if q:
            dose_pct = _safe_float(q.dose_maxima_legal_pct)
            if dose_pct is None or dose_pct <= 0:
                dose_pct = _safe_float(q.dose_maxima_tecnica_pct)
            if dose_pct is None or dose_pct <= 0:
                dose_pct = 0.05
            forced_quelante_lb_kg = (volume_l * float(dose_pct)) / 100.0
            if forced_quelante_lb_kg > 0:
                nm = f"{q.nome} ({q.abreviatura})" if (q.abreviatura or "").strip() else (q.nome or "Quelante")
                valid_insumos.append(Insumo(
                    id=str(q.id),
                    nome=nm,
                    solubilidade="Totalmente miscível",
                    natureza_fisica="Líquida",
                    teor_por_nutriente_pct={},
                    rank_solubilidade=1,
                    rank_custo=1,
                    fator_v=0.0,
                    preco_unit=float(q.preco_unit or 0.0),
                    fornecedor="Aditivo",
                    lead_time="N/A",
                    is_local=False,
                ))
                forced_quelante_idx = len(valid_insumos) - 1

    nutrient_keys = [k for k, _ in NUTRIENT_COLUMNS if (targets.get(k, 0.0) or 0.0) > 0]
    num_insumos = len(valid_insumos)
    
    A_eq = []
    for k in nutrient_keys:
        if k == "S":
            row = [_effective_teor_pct(i, "S") / 100.0 for i in valid_insumos]
        else:
            row = [float(i.teor_por_nutriente_pct.get(k, 0.0) or 0.0) / 100.0 for i in valid_insumos]
        A_eq.append(row)
    
    b_eq = [targets.get(k, 0.0) * volume_l / 100.0 for k in nutrient_keys]

    forms: List[List[FormulaLine]] = []
    
    for tier, multiplier in [(1, 1.0), (2, 1.5), (3, 100.0)]:
        sol_limits = [_solubility_limit_mass_kg(i, volume_l) for i in valid_insumos]
        has_sol_limits = any((v is not None and v > 0) for v in sol_limits)
        base_bounds: List[Tuple[float, Optional[float]]] = []
        for j, ins in enumerate(valid_insumos):
            lb = forced_quelante_lb_kg if (forced_quelante_idx is not None and j == forced_quelante_idx) else 0.0
            base_bounds.append((float(lb), None))

        blocked_names = set()
        for var_idx in range(4):
            c = [i.preco_unit * (100.0 if i.nome in blocked_names else 1.0) for i in valid_insumos]

            A_ub: List[List[float]] = [[i.fator_v for i in valid_insumos]]
            b_ub: List[float] = [volume_l]

            for j, ins in enumerate(valid_insumos):
                ub = _solubility_cap_mass_kg(ins, volume_l, targets, multiplier)
                if ub is None:
                    continue
                row = [0.0 for _ in range(num_insumos)]
                row[j] = 1.0
                A_ub.append(row)
                b_ub.append(float(ub))

            if has_sol_limits:
                row = [(1.0 / float(sol_limits[j])) if (sol_limits[j] is not None and sol_limits[j] > 0) else 0.0 for j in range(num_insumos)]
                A_ub.append(row)
                b_ub.append(1.0)

            cap_nutrients = ("N", "P2O5", "K2O", "S", "Ca")
            for nk in cap_nutrients:
                target_pct = float(targets.get(nk, 0.0) or 0.0)
                if target_pct <= 0:
                    continue
                cap_pct = target_pct * cap_share
                cap_mass = (cap_pct * volume_l) / 100.0
                if cap_mass <= 0:
                    continue
                for j, ins in enumerate(valid_insumos):
                    teor = _effective_teor_pct(ins, nk)
                    if teor <= 0:
                        continue
                    row = [0.0 for _ in range(num_insumos)]
                    row[j] = float(teor) / 100.0
                    A_ub.append(row)
                    b_ub.append(float(cap_mass))

            if tier == 1:
                for rule in SPLIT_RULES:
                    if int(rule.get("tier", 0)) != tier:
                        continue
                    nutrient = str(rule.get("nutrient", "")).strip()
                    if not nutrient:
                        continue
                    threshold = float(rule.get("threshold_pct", 0.0) or 0.0)
                    target_pct_total = float(targets.get(nutrient, 0.0) or 0.0)
                    if target_pct_total < threshold or target_pct_total <= 0:
                        continue
                    total_kg = (target_pct_total * volume_l) / 100.0
                    if total_kg <= 0:
                        continue
                    min_family_shares = rule.get("min_family_shares") or {}
                    if not isinstance(min_family_shares, dict):
                        continue
                    for fam, share in min_family_shares.items():
                        fam_name = str(fam).strip()
                        min_share = float(share or 0.0)
                        if not fam_name or min_share <= 0:
                            continue
                        fam_idxs = [j for j, ins in enumerate(valid_insumos) if (nutrient in ins.teor_por_nutriente_pct) and _insumo_is_family(ins, fam_name)]
                        if not fam_idxs:
                            continue
                        row = [0.0 for _ in range(num_insumos)]
                        for j in fam_idxs:
                            row[j] = -(valid_insumos[j].teor_por_nutriente_pct.get(nutrient, 0.0) / 100.0)
                        A_ub.append(row)
                        b_ub.append(-(min_share * total_kg))

            bounds = base_bounds

            def solve(a_ub: List[List[float]], b_ub_local: List[float]):
                return linprog(c, A_ub=a_ub, b_ub=b_ub_local, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")

            res = solve(A_ub, b_ub)
            if res.success and has_sol_limits:
                fracs = []
                total_frac = 0.0
                for j in range(num_insumos):
                    lim = sol_limits[j]
                    if lim is None or lim <= 0:
                        fracs.append(0.0)
                        continue
                    f = max(0.0, float(res.x[j])) / float(lim)
                    fracs.append(f)
                    total_frac += f

                if total_frac >= 0.995:
                    idx_max = max(range(num_insumos), key=lambda j: fracs[j])
                    if fracs[idx_max] >= 0.90 and (sum(1 for f in fracs if f >= 0.05) <= 1):
                        lim_max = sol_limits[idx_max]
                        if lim_max is not None and lim_max > 0:
                            a2 = list(A_ub)
                            b2 = list(b_ub)
                            row2 = [0.0 for _ in range(num_insumos)]
                            row2[idx_max] = 1.0
                            a2.append(row2)
                            b2.append(0.85 * float(lim_max))
                            res2 = solve(a2, b2)
                            if res2.success:
                                res = res2

            if res.success:
                best_lines = []
                max_mass = 0.0
                max_insumo = None
                for idx_val, x_val in enumerate(res.x):
                    if x_val > 0.001:
                        ins = valid_insumos[idx_val]
                        contrib = _contrib_pct_map(volume_l, float(x_val), ins)
                        best_lines.append(FormulaLine(ins.nome, x_val, contrib, ins.preco_unit, x_val * ins.preco_unit, ins.fornecedor, ins.lead_time, ins.is_local))
                        if x_val > max_mass:
                            max_mass = x_val
                            max_insumo = ins.nome

                if tier == 2:
                    massa_glicerina = volume_l * 0.02
                    best_lines.append(FormulaLine("Glicerina (Co-solvente)", massa_glicerina, {}, 4.00, massa_glicerina * 4.00, is_local=False))
                elif tier == 3:
                    massa_sorbitol = volume_l * 0.05
                    best_lines.append(FormulaLine("Sorbitol 70% (Co-solvente)", massa_sorbitol, {}, 5.00, massa_sorbitol * 5.00, is_local=False))
                
                forms.append(best_lines)
                if max_insumo:
                    blocked_names.add(max_insumo)
            else:
                forms.append([])

    while len(forms) < 12:
        forms.append([])
        
    return forms
