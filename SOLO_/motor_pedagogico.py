from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


BASE_FILE = Path(__file__).with_name("base_pedagogica_quimica.json")


def carregar_base_pedagogica(path: Optional[Path] = None) -> Dict[str, Any]:
    arquivo = Path(path) if path else BASE_FILE
    return json.loads(arquivo.read_text(encoding="utf-8"))


def indexar_conceitos(base: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {str(item["id"]): dict(item) for item in base.get("conceitos", [])}


def classificar_indice_saturacao(valor: Optional[float]) -> str:
    if valor is None:
        return "não informado"
    if valor >= 1.0:
        return "crítico"
    if valor >= 0.85:
        return "elevado"
    if valor >= 0.60:
        return "moderado"
    return "seguro"


def classificar_carga_salina(valor: Optional[float]) -> str:
    if valor is None:
        return "não informada"
    if valor > 45:
        return "alta"
    if valor >= 30:
        return "moderada"
    return "baixa"


def classificar_ph(valor: Optional[float]) -> str:
    if valor is None:
        return "não informado"
    if valor < 3.0:
        return "muito ácido"
    if valor > 7.0:
        return "alcalino"
    if valor > 5.5:
        return "acima da faixa ideal para metais"
    return "faixa favorável"


def classificar_forca_ionica(valor: Optional[float]) -> str:
    if valor is None:
        return "não informada"
    if valor > 2.0:
        return "muito alta"
    if valor > 1.0:
        return "elevada"
    return "dentro do esperado"


def _obter(snapshot: Dict[str, Any], chave: str, padrao: Any = None) -> Any:
    return snapshot.get(chave, padrao)


def _linhas_para_texto(linhas: Iterable[Dict[str, Any]]) -> List[str]:
    saida: List[str] = []
    for item in linhas:
        nome = str(item.get("insumo_nome") or "").strip()
        massa = item.get("massa_kg")
        if nome:
            if massa is None:
                saida.append(f"- {nome}")
            else:
                saida.append(f"- {nome}: {float(massa):.3f} kg")
    return saida


def selecionar_conceitos(snapshot: Dict[str, Any], base: Dict[str, Any]) -> List[str]:
    ids: List[str] = ["indice_saturacao", "carga_salina", "tiers"]

    triggered_pairs = list(_obter(snapshot, "pares_criticos", []))
    aditivos = list(_obter(snapshot, "aditivos_sugeridos", []))
    ph = _obter(snapshot, "ph_teorico")
    ionic = _obter(snapshot, "forca_ionica")
    hlb = _obter(snapshot, "hlb_requerido")
    thermal = _obter(snapshot, "balanco_termico", {}) or {}
    sat = _obter(snapshot, "indice_saturacao")
    modo_sc = bool(_obter(snapshot, "modo_sc", False))

    if triggered_pairs:
        ids.append("pares_kps")
    if ph is not None:
        ids.append("ph_teorico")
    if ionic is not None:
        ids.append("forca_ionica")
    if hlb is not None:
        ids.append("hlb")
    if thermal:
        ids.append("balance_termico")
    if modo_sc or (sat is not None and float(sat) > 1.10):
        ids.append("reologia")
    if aditivos:
        ids.append("aditivos")

    conceitos = indexar_conceitos(base)
    return [cid for cid in ids if cid in conceitos]


def construir_contexto_formula(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    sat = _obter(snapshot, "indice_saturacao")
    carga = _obter(snapshot, "carga_salina_pct_mv")
    ph = _obter(snapshot, "ph_teorico")
    ionic = _obter(snapshot, "forca_ionica")

    contexto: Dict[str, Any] = {
        "nome_formula": _obter(snapshot, "nome_formula", "Fórmula sem nome"),
        "tier": _obter(snapshot, "tier", "N/D"),
        "volume_l": _obter(snapshot, "volume_l"),
        "temperatura_c": _obter(snapshot, "temperatura_c"),
        "indice_saturacao": sat,
        "classe_saturacao": classificar_indice_saturacao(float(sat)) if sat is not None else "não informado",
        "carga_salina_pct_mv": carga,
        "classe_carga_salina": classificar_carga_salina(float(carga)) if carga is not None else "não informada",
        "ph_teorico": ph,
        "classe_ph": classificar_ph(float(ph)) if ph is not None else "não informado",
        "forca_ionica": ionic,
        "classe_forca_ionica": classificar_forca_ionica(float(ionic)) if ionic is not None else "não informada",
        "pares_criticos": list(_obter(snapshot, "pares_criticos", [])),
        "aditivos_sugeridos": list(_obter(snapshot, "aditivos_sugeridos", [])),
        "linhas": list(_obter(snapshot, "linhas", [])),
        "balanco_termico": dict(_obter(snapshot, "balanco_termico", {}) or {}),
        "hlb_requerido": _obter(snapshot, "hlb_requerido"),
        "modo_sc": bool(_obter(snapshot, "modo_sc", False)),
        "resumo_risco": _obter(snapshot, "resumo_risco", ""),
    }
    return contexto


def montar_fatos_dinamicos(conceito_id: str, contexto: Dict[str, Any]) -> List[str]:
    fatos: List[str] = []

    if conceito_id == "indice_saturacao":
        fatos.append(
            f"Índice de saturação calculado: {contexto['indice_saturacao'] if contexto['indice_saturacao'] is not None else 'N/D'} "
            f"({contexto['classe_saturacao']})."
        )
    elif conceito_id == "carga_salina":
        fatos.append(
            f"Carga salina estimada: {contexto['carga_salina_pct_mv'] if contexto['carga_salina_pct_mv'] is not None else 'N/D'}% m/v "
            f"({contexto['classe_carga_salina']})."
        )
    elif conceito_id == "pares_kps":
        pares = contexto.get("pares_criticos", [])
        if pares:
            fatos.append("Pares críticos detectados: " + ", ".join(str(p) for p in pares) + ".")
        else:
            fatos.append("Nenhum par crítico foi informado no snapshot.")
    elif conceito_id == "balance_termico":
        bt = contexto.get("balanco_termico", {})
        if bt:
            tin = bt.get("temp_entrada_c", "N/D")
            tout = bt.get("temp_saida_c", "N/D")
            dt = bt.get("delta_t_c", "N/D")
            fatos.append(f"Temperatura de entrada: {tin} °C | saída estimada: {tout} °C | ΔT: {dt} °C.")
        else:
            fatos.append("Não há dados de balanço térmico para esta fórmula.")
    elif conceito_id == "ph_teorico":
        fatos.append(
            f"pH teórico estimado: {contexto['ph_teorico'] if contexto['ph_teorico'] is not None else 'N/D'} "
            f"({contexto['classe_ph']})."
        )
    elif conceito_id == "forca_ionica":
        fatos.append(
            f"Força iônica estimada: {contexto['forca_ionica'] if contexto['forca_ionica'] is not None else 'N/D'} "
            f"({contexto['classe_forca_ionica']})."
        )
    elif conceito_id == "hlb":
        fatos.append(f"HLB requerido estimado: {contexto.get('hlb_requerido', 'N/D')}.")
    elif conceito_id == "reologia":
        fatos.append("A fórmula foi marcada como modo SC." if contexto.get("modo_sc") else "A fórmula foi tratada como solução sem modo SC explícito.")
    elif conceito_id == "aditivos":
        aditivos = contexto.get("aditivos_sugeridos", [])
        if aditivos:
            fatos.append("Aditivos sugeridos: " + ", ".join(str(a) for a in aditivos) + ".")
        else:
            fatos.append("Não há aditivos sugeridos neste snapshot.")
    elif conceito_id == "tiers":
        fatos.append(f"A fórmula foi classificada como Tier {contexto.get('tier', 'N/D')}.")

    return fatos


def renderizar_secao_pedagogica(conceito: Dict[str, Any], contexto: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": conceito["id"],
        "titulo": conceito["titulo"],
        "explicacao_intuitiva": conceito["explicacao_intuitiva"],
        "explicacao_tecnica": conceito["explicacao_tecnica"],
        "matematica": conceito["matematica"],
        "logica_algoritmica": conceito["logica_algoritmica"],
        "python_iniciante": conceito["python_iniciante"],
        "perguntas_guia": list(conceito.get("perguntas_guia", [])),
        "fatos_dinamicos": montar_fatos_dinamicos(str(conceito["id"]), contexto),
    }


def explicar_formula(snapshot: Dict[str, Any], base: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    base = base or carregar_base_pedagogica()
    conceitos = indexar_conceitos(base)
    contexto = construir_contexto_formula(snapshot)
    conceitos_ativos = selecionar_conceitos(snapshot, base)

    secoes: List[Dict[str, Any]] = []
    for conceito_id in conceitos_ativos:
        secoes.append(renderizar_secao_pedagogica(conceitos[conceito_id], contexto))

    resumo = [
        f"Fórmula: {contexto['nome_formula']}",
        f"Tier: {contexto['tier']}",
        f"Saturação: {contexto['classe_saturacao']}",
        f"Carga salina: {contexto['classe_carga_salina']}",
    ]
    if contexto.get("classe_ph") != "não informado":
        resumo.append(f"pH: {contexto['classe_ph']}")
    if contexto.get("resumo_risco"):
        resumo.append(str(contexto["resumo_risco"]))

    return {
        "metadados": {
            "fonte_base": str(BASE_FILE.name),
            "nome_formula": contexto["nome_formula"],
        },
        "resumo_executivo": resumo,
        "linhas_formula": _linhas_para_texto(contexto.get("linhas", [])),
        "secoes": secoes,
    }


def renderizar_texto_explicacao(snapshot: Dict[str, Any], base: Optional[Dict[str, Any]] = None) -> str:
    explicacao = explicar_formula(snapshot, base=base)
    linhas: List[str] = []

    linhas.append(f"EXPLICAÇÃO PEDAGÓGICA — {explicacao['metadados']['nome_formula']}")
    linhas.append("")
    linhas.append("Resumo executivo:")
    for item in explicacao["resumo_executivo"]:
        linhas.append(f"- {item}")

    if explicacao["linhas_formula"]:
        linhas.append("")
        linhas.append("Composição informada:")
        linhas.extend(explicacao["linhas_formula"])

    for secao in explicacao["secoes"]:
        linhas.append("")
        linhas.append("=" * 72)
        linhas.append(secao["titulo"])
        linhas.append("=" * 72)
        linhas.append("Intuição:")
        linhas.append(secao["explicacao_intuitiva"])
        linhas.append("")
        linhas.append("Técnico:")
        linhas.append(secao["explicacao_tecnica"])
        linhas.append("")
        linhas.append("Matemática:")
        linhas.append(secao["matematica"])
        linhas.append("")
        linhas.append("Lógica:")
        linhas.append(secao["logica_algoritmica"])
        linhas.append("")
        linhas.append("Python para iniciante:")
        linhas.append(secao["python_iniciante"])

        if secao["fatos_dinamicos"]:
            linhas.append("")
            linhas.append("Fatos desta fórmula:")
            for fato in secao["fatos_dinamicos"]:
                linhas.append(f"- {fato}")

        if secao["perguntas_guia"]:
            linhas.append("")
            linhas.append("Perguntas-guia:")
            for pergunta in secao["perguntas_guia"]:
                linhas.append(f"- {pergunta}")

    return "\n".join(linhas).strip() + "\n"


if __name__ == "__main__":
    exemplo_snapshot = {
        "nome_formula": "F1",
        "tier": 1,
        "volume_l": 100.0,
        "temperatura_c": 25.0,
        "indice_saturacao": 0.91,
        "carga_salina_pct_mv": 38.5,
        "ph_teorico": 4.8,
        "forca_ionica": 1.2,
        "pares_criticos": ["Ca + SO4"],
        "aditivos_sugeridos": ["EDTA", "Estabilizante anti-cristalização"],
        "linhas": [
            {"insumo_nome": "Ureia", "massa_kg": 20.0},
            {"insumo_nome": "MAP", "massa_kg": 15.0},
            {"insumo_nome": "Nitrato de cálcio", "massa_kg": 8.0}
        ],
        "balanco_termico": {
            "temp_entrada_c": 25.0,
            "temp_saida_c": 17.5,
            "delta_t_c": -7.5
        },
        "modo_sc": False,
        "resumo_risco": "Fórmula operacional, mas com margem reduzida de estabilidade."
    }

    print(renderizar_texto_explicacao(exemplo_snapshot))
