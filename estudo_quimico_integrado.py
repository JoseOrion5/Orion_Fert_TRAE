"""
Camada de integração pedagógica para o estudo químico.

Uso recomendado no projeto existente:

    import estudo_quimico_integrado as estudo_quimico

Assim, chamadas existentes para `estudo_quimico.gerar_estudo_completo(...)`
continuam funcionando, mas passam a incluir seções pedagógicas baseadas na
base `base_pedagogica_quimica.json`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from motor_pedagogico import explicar_formula

RAW_DICT_MARKERS = ("{'tipo':", "{'dados':", "{'titulo':", '{"tipo":', '{"dados":', '{"titulo":')


@dataclass
class SecaoEstudo:
    titulo: str
    quimica: str = ""
    matematica: str = ""
    logica: str = ""
    python: str = ""
    dados: Optional[Dict[str, Any]] = None
    alerta: Optional[str] = None
    recomendacao: Optional[str] = None


def _tier_from_idx(idx: int) -> int:
    return 1 if 1 <= idx <= 4 else (2 if 5 <= idx <= 8 else 3)


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        text = value
    elif isinstance(value, (int, float, bool)):
        text = str(value)
    elif isinstance(value, (list, tuple)):
        bits = []
        for item in value:
            if isinstance(item, (str, int, float, bool)):
                bits.append(str(item))
        text = "\n".join(x for x in bits if x)
    else:
        return default
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    for marker in RAW_DICT_MARKERS:
        if marker in text:
            return ""
    return text


def _safe_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _safe_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _totais_from_lines(lines: Sequence[Any]) -> Dict[str, float]:
    totais: Dict[str, float] = {}
    for l in lines or []:
        contrib = getattr(l, "contrib_pct", {}) or {}
        for k, v in contrib.items():
            try:
                totais[str(k)] = float(totais.get(str(k), 0.0) or 0.0) + float(v or 0.0)
            except Exception:
                continue
    return totais


def _sanitize_field_text(value: Any) -> str:
    return _safe_text(value)


def _sanitize_dados(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, dict):
        return dict(value)
    return None


def _listar_aditivos(output: Any) -> List[str]:
    saida: List[str] = []
    for sug in list(getattr(output, "aditivos_sugeridos", []) or []):
        try:
            a = getattr(sug, "aditivo", None)
            nome = getattr(a, "nome", None) if a is not None else None
            motivo = getattr(sug, "motivo", None)
            if nome and motivo:
                saida.append(f"{nome} ({motivo})")
            elif nome:
                saida.append(str(nome))
        except Exception:
            continue
    return saida


def _listar_linhas(lines: Sequence[Any]) -> List[Dict[str, Any]]:
    saida: List[Dict[str, Any]] = []
    for l in lines or []:
        saida.append(
            {
                "insumo_nome": getattr(l, "insumo_nome", None),
                "massa_kg": _safe_float(getattr(l, "massa_kg", None)),
            }
        )
    return saida


def _build_snapshot(
    idx: int,
    output: Any,
    insumos: Sequence[Any],
    targets: Dict[str, float],
    volume_l: float,
    temp_c: float,
) -> Dict[str, Any]:
    try:
        from motor import (
            _calculate_required_hlb_from_lines,
            _estimate_ionic_strength,
            _estimate_ph_theoretical,
            _kps_triggered_pairs,
            _thermal_balance_estimate,
        )
    except Exception:
        _calculate_required_hlb_from_lines = None
        _estimate_ionic_strength = None
        _estimate_ph_theoretical = None
        _kps_triggered_pairs = None
        _thermal_balance_estimate = None

    lines = list(getattr(output, "lines", []) or [])
    sat = _safe_float(getattr(output, "indice_saturacao", None))
    massa_total = sum(float(getattr(l, "massa_kg", 0.0) or 0.0) for l in lines)
    carga = (massa_total / float(volume_l) * 100.0) if volume_l else None
    ph_est = _estimate_ph_theoretical(lines, volume_l) if callable(_estimate_ph_theoretical) else None
    ionic = _estimate_ionic_strength(lines, volume_l, ph_est=ph_est) if callable(_estimate_ionic_strength) else None
    thermal = _thermal_balance_estimate(lines, insumos, volume_l, temp_c) if callable(_thermal_balance_estimate) else {}
    thermal = thermal or {}
    hlb = _calculate_required_hlb_from_lines(lines) if callable(_calculate_required_hlb_from_lines) else None
    totais = _totais_from_lines(lines)
    pares = _kps_triggered_pairs(totais, targets) if callable(_kps_triggered_pairs) else []
    pares = pares or []

    modo_sc = bool(sat is not None and float(sat) > 1.10)
    tier = _tier_from_idx(idx)

    if sat is None:
        resumo = "Formulação sem índice de saturação disponível."
    elif sat >= 1.0:
        resumo = "Formulação em faixa crítica de estabilidade."
    elif sat >= 0.85:
        resumo = "Formulação operacional, mas com margem reduzida de estabilidade."
    else:
        resumo = "Formulação em faixa mais confortável de estabilidade."

    return {
        "nome_formula": f"F{idx}",
        "tier": tier,
        "volume_l": float(volume_l),
        "temperatura_c": float(temp_c),
        "indice_saturacao": sat,
        "carga_salina_pct_mv": round(float(carga), 3) if carga is not None else None,
        "ph_teorico": _safe_float(ph_est),
        "forca_ionica": _safe_float(ionic),
        "pares_criticos": [_safe_text(p) for p in pares if _safe_text(p)],
        "aditivos_sugeridos": _listar_aditivos(output),
        "linhas": _listar_linhas(lines),
        "balanco_termico": {
            "temp_entrada_c": float(temp_c),
            "temp_saida_c": _safe_float(thermal.get("temp_out_c")),
            "delta_t_c": _safe_float(thermal.get("delta_t_c")),
            "calor_total_kj": _safe_float(thermal.get("q_kj")),
        },
        "hlb_requerido": _safe_float(hlb),
        "modo_sc": modo_sc,
        "resumo_risco": resumo,
    }


def _render_resumo_pedagogico(explicacao: Dict[str, Any], snapshot: Dict[str, Any]) -> SecaoEstudo:
    resumo = "\n".join(f"• {item}" for item in _safe_list(explicacao.get("resumo_executivo")))
    linhas = "\n".join(_safe_text(item) for item in _safe_list(explicacao.get("linhas_formula")) if _safe_text(item))

    quimica = (
        "Esta seção resume a leitura didática da fórmula antes do detalhamento conceito a conceito.\n\n"
        f"{resumo}"
    ).strip()
    if linhas:
        quimica += f"\n\nComposição informada:\n{linhas}"

    alerta = None
    sat = snapshot.get("indice_saturacao")
    if sat is not None:
        if float(sat) >= 1.0:
            alerta = "Leitura pedagógica: a fórmula está em zona crítica de solubilidade."
        elif float(sat) >= 0.85:
            alerta = "Leitura pedagógica: a fórmula está próxima do limite operacional."

    recomendacao = "Use esta visão como introdução antes de estudar cada conceito isoladamente."
    return SecaoEstudo(
        titulo="Leitura Pedagógica da Fórmula",
        quimica=_sanitize_field_text(quimica),
        recomendacao=recomendacao,
        alerta=alerta,
        dados={
            "tipo": "resumo_pedagogico",
            "resumo_executivo": [item for item in _safe_list(explicacao.get("resumo_executivo")) if _safe_text(item)],
            "linhas_formula": [item for item in _safe_list(explicacao.get("linhas_formula")) if _safe_text(item)],
        },
    )


def _render_secao_pedagogica(secao: Dict[str, Any]) -> SecaoEstudo:
    fatos_list = [_safe_text(f) for f in _safe_list(secao.get("fatos_dinamicos")) if _safe_text(f)]
    perguntas_list = [_safe_text(p) for p in _safe_list(secao.get("perguntas_guia")) if _safe_text(p)]
    fatos = "\n".join(f"• {f}" for f in fatos_list)
    perguntas = "\n".join(f"• {p}" for p in perguntas_list)

    quimica = (
        f"Intuição:\n{_safe_text(secao.get('explicacao_intuitiva'))}\n\n"
        f"Química técnica:\n{_safe_text(secao.get('explicacao_tecnica'))}"
    ).strip()

    logica = _safe_text(secao.get("logica_algoritmica"))
    if fatos:
        logica += f"\n\nFatos desta fórmula:\n{fatos}"
    if perguntas:
        logica += f"\n\nPerguntas-guia:\n{perguntas}"

    return SecaoEstudo(
        titulo=f"Pedagogia — {_safe_text(secao.get('titulo'), 'Conceito')}",
        quimica=_sanitize_field_text(quimica),
        matematica=_sanitize_field_text(secao.get("matematica")),
        logica=_sanitize_field_text(logica),
        python=_sanitize_field_text(secao.get("python_iniciante")),
        dados=_sanitize_dados(secao.get("dados")) or {
            "tipo": "pedagogico",
            "fatos_dinamicos": fatos_list,
            "perguntas_guia": perguntas_list,
        },
    )


def _try_import_base_module() -> Any:
    try:
        import estudo_quimico as modulo_base
        if Path(getattr(modulo_base, "__file__", "")).resolve() == Path(__file__).resolve():
            return None
        return modulo_base
    except Exception:
        return None


def _copy_base_section(s: Any) -> SecaoEstudo:
    return SecaoEstudo(
        titulo=_sanitize_field_text(getattr(s, "titulo", "") or ""),
        quimica=_sanitize_field_text(getattr(s, "quimica", "") or ""),
        matematica=_sanitize_field_text(getattr(s, "matematica", "") or ""),
        logica=_sanitize_field_text(getattr(s, "logica", "") or ""),
        python=_sanitize_field_text(getattr(s, "python", "") or ""),
        dados=_sanitize_dados(getattr(s, "dados", None)),
        alerta=_sanitize_field_text(getattr(s, "alerta", None)) or None,
        recomendacao=_sanitize_field_text(getattr(s, "recomendacao", None)) or None,
    )


def _contains_raw_dict_markers(text: str) -> bool:
    return any(marker in text for marker in RAW_DICT_MARKERS)


def executar_teste_rapido() -> None:
    class DummyLine:
        def __init__(self, insumo_nome: str, massa_kg: float, contrib_pct: Optional[Dict[str, float]] = None):
            self.insumo_nome = insumo_nome
            self.massa_kg = massa_kg
            self.contrib_pct = contrib_pct or {}

    class DummyOutput:
        def __init__(self):
            self.lines = [
                DummyLine("Ureia", 18.0, {"N": 8.0}),
                DummyLine("MAP", 12.0, {"N": 2.0, "P2O5": 6.0}),
                DummyLine("Nitrato de cálcio", 7.0, {"Ca": 4.0}),
            ]
            self.indice_saturacao = 0.92
            self.aditivos_sugeridos = []

    secoes = gerar_estudo_completo(
        idx=1,
        output=DummyOutput(),
        insumos=[],
        targets={"N": 10.0, "P2O5": 6.0, "Ca": 4.0},
        volume_l=100.0,
        temp_c=25.0,
    )

    assert isinstance(secoes, list) and secoes, "A função deve retornar uma lista de seções."
    assert secoes[0].titulo == "Leitura Pedagógica da Fórmula", "A primeira seção deve ser a leitura pedagógica."
    assert any(sec.titulo.startswith("Pedagogia — ") for sec in secoes[1:]), "Devem existir seções pedagógicas."
    assert any("\n" in (sec.python or "") for sec in secoes[1:]), "O campo python deve conter snippet multi-linha."
    assert any("=" in (sec.matematica or "") or "μ =" in (sec.matematica or "") for sec in secoes[1:]), "O campo matemática deve conter fórmula."

    for sec in secoes:
        for text in (sec.quimica, sec.matematica, sec.logica, sec.python):
            assert not _contains_raw_dict_markers(text or ""), "Nenhum campo textual pode conter dict raw."

    print("Teste rápido OK: leitura pedagógica + seções pedagógicas válidas.")


def gerar_estudo_completo(
    idx: int,
    output: Any,
    insumos: Sequence[Any],
    targets: Dict[str, float],
    volume_l: float,
    temp_c: float,
) -> List[SecaoEstudo]:
    """
    Compatível com a assinatura do módulo original.

    Fluxo:
    1. tenta gerar o estudo químico base já existente
    2. monta um snapshot da fórmula
    3. usa o motor pedagógico para enriquecer o estudo
    4. retorna tudo em uma lista de seções compatíveis com `build_study_view(...)`
    """
    secoes: List[SecaoEstudo] = []

    modulo_base = _try_import_base_module()
    if modulo_base is not None:
        try:
            base_sections = modulo_base.gerar_estudo_completo(idx, output, insumos, targets, volume_l, temp_c)
            for s in list(base_sections or []):
                secoes.append(_copy_base_section(s))
        except Exception:
            pass

    snapshot = _build_snapshot(idx, output, insumos, targets, volume_l, temp_c)
    explicacao = explicar_formula(snapshot)

    secoes.append(_render_resumo_pedagogico(explicacao, snapshot))
    for secao in explicacao.get("secoes", []):
        secoes.append(_render_secao_pedagogica(secao))

    return secoes


if __name__ == "__main__":
    executar_teste_rapido()
