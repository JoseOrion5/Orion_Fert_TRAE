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
from typing import Any, Dict, List, Optional, Sequence

from motor_pedagogico import explicar_formula


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
            else:
                saida.append(str(sug))
        except Exception:
            saida.append(str(sug))
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
    from motor import (
        _calculate_required_hlb_from_lines,
        _estimate_ionic_strength,
        _estimate_ph_theoretical,
        _kps_triggered_pairs,
        _thermal_balance_estimate,
    )

    lines = list(getattr(output, "lines", []) or [])
    sat = _safe_float(getattr(output, "indice_saturacao", None))
    massa_total = sum(float(getattr(l, "massa_kg", 0.0) or 0.0) for l in lines)
    carga = (massa_total / float(volume_l) * 100.0) if volume_l else None
    ph_est = _estimate_ph_theoretical(lines, volume_l)
    ionic = _estimate_ionic_strength(lines, volume_l, ph_est=ph_est)
    thermal = _thermal_balance_estimate(lines, insumos, volume_l, temp_c) or {}
    hlb = _calculate_required_hlb_from_lines(lines)
    totais = _totais_from_lines(lines)
    pares = _kps_triggered_pairs(totais, targets) or []

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
        "pares_criticos": [str(p) for p in pares],
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
    resumo = "\n".join(f"• {item}" for item in explicacao.get("resumo_executivo", []))
    linhas = "\n".join(explicacao.get("linhas_formula", []))

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
        quimica=quimica,
        recomendacao=recomendacao,
        alerta=alerta,
    )


def _render_secao_pedagogica(secao: Dict[str, Any]) -> SecaoEstudo:
    fatos = "\n".join(f"• {f}" for f in secao.get("fatos_dinamicos", []) if str(f).strip())
    perguntas = "\n".join(f"• {p}" for p in secao.get("perguntas_guia", []) if str(p).strip())

    quimica = (
        f"Intuição:\n{secao.get('explicacao_intuitiva', '').strip()}\n\n"
        f"Técnico:\n{secao.get('explicacao_tecnica', '').strip()}"
    ).strip()

    logica = secao.get("logica_algoritmica", "").strip()
    if fatos:
        logica += f"\n\nFatos desta fórmula:\n{fatos}"
    if perguntas:
        logica += f"\n\nPerguntas-guia:\n{perguntas}"

    return SecaoEstudo(
        titulo=f"Pedagogia — {secao.get('titulo', 'Conceito')}",
        quimica=quimica,
        matematica=secao.get("matematica", "").strip(),
        logica=logica.strip(),
        python=secao.get("python_iniciante", "").strip(),
    )


def _try_import_base_module() -> Any:
    try:
        import estudo_quimico as modulo_base
        return modulo_base
    except Exception:
        return None


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
                secoes.append(
                    SecaoEstudo(
                        titulo=str(getattr(s, "titulo", "") or ""),
                        quimica=str(getattr(s, "quimica", "") or ""),
                        matematica=str(getattr(s, "matematica", "") or ""),
                        logica=str(getattr(s, "logica", "") or ""),
                        python=str(getattr(s, "python", "") or ""),
                        dados=getattr(s, "dados", None),
                        alerta=getattr(s, "alerta", None),
                        recomendacao=getattr(s, "recomendacao", None),
                    )
                )
        except Exception:
            pass

    snapshot = _build_snapshot(idx, output, insumos, targets, volume_l, temp_c)
    explicacao = explicar_formula(snapshot)

    secoes.append(_render_resumo_pedagogico(explicacao, snapshot))
    for secao in explicacao.get("secoes", []):
        secoes.append(_render_secao_pedagogica(secao))

    return secoes
