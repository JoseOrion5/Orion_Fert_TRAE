from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

__all__ = [
    "COMPLETAO_DIR",
    "COMPLETAO_XLSX",
    "BASE_UNICA_FILE",
    "DB_PATH",
    "DEFAULT_VOLUME_L",
    "NUTRIENT_COLUMNS",
    "S_FROM_SO4_MASS_RATIO",
    "SOLUBILITY_NUTRIENT_PCT_CAPS",
    "FAMILY_KEYWORDS",
    "SPLIT_RULES",
    "KPS_ALERT_TEXT",
    "KPS_PARES_PROIBIDOS",
    "BLOCKED_INSUMO_PATTERNS",
    "BLOCKED_OBS_LABELS",
]


BASE_DIR = Path(__file__).resolve().parent.parent
COMPLETAO_DIR = BASE_DIR / "COMPLETAO"
COMPLETAO_XLSX = COMPLETAO_DIR / "COMPLETAO.xlsx"
BASE_UNICA_FILE = COMPLETAO_DIR / "DATABASE_MESTRE_ORION.xlsx"
DB_PATH = BASE_DIR / "orion_agroquim.db"

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
    "nitrato_amonio": ("nitrato de amonio", "nitrato de amônio", "nitrato de amonia", "nitrato de amônia"),
    "acido_borico": ("acido borico", "ácido bórico"),
    "k_cloreto": ("cloreto de potassio", "cloreto de potássio", "kcl"),
    "k_nitrato": ("nitrato de potassio", "nitrato de potássio", "kno3"),
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
    {"tier": 1, "nutrient": "K2O", "threshold_pct": 8.0, "min_family_shares": {"k_cloreto": 0.30, "k_nitrato": 0.30}},
]

KPS_ALERT_TEXT = "Risco de precipitação detectado: Requer complexação química"

KPS_PARES_PROIBIDOS: Dict[Tuple[str, str], Dict[str, Any]] = {
    ("Ca", "SO4"): {"risco": "Gesso (CaSO4)", "agente_quelante": "EDTA", "dose_pct": 0.05},
    ("Mg", "P2O5"): {"risco": "Fosfatos de magnésio", "agente_quelante": "EDTA", "dose_pct": 0.05},
    ("Ca", "P2O5"): {"risco": "Fosfatos de cálcio", "agente_quelante": "EDTA", "dose_pct": 0.05},
}

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
