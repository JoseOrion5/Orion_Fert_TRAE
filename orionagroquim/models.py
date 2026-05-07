from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

__all__ = [
    "ThermoStatus",
    "Insumo",
    "FormulaLine",
    "Aditivo",
    "AditivoSuggestion",
    "RelatorioOP",
    "FormulaOutput",
]


@dataclass
class ThermoStatus:
    agua_negativa: bool
    densidade_critica: bool
    agua_balanco_kg: float
    densidade_calculada: float
    is_supersaturado: bool
    tech_tier: int = 1
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
    hlb: float = 0.0
    limite_forca_ionica: float = 0.0
    tipo_reologia: str = ""


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


@dataclass(frozen=True)
class FormulaOutput:
    lines: List[FormulaLine]
    process_steps: List[str]
    aditivos_sugeridos: List[AditivoSuggestion]
    instrucoes_producao: List[str]
    aditivos: List[Dict[str, float]]
    indice_saturacao: float
