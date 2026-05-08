from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


BASE_FILE = Path(__file__).with_name("base_pedagogica_quimica.json")
RAW_DICT_MARKERS = ("{'tipo':", "{'dados':", "{'titulo':", '{"tipo":', '{"dados":', '{"titulo":')
REQUIRED_CONCEPT_KEYS = (
    "explicacao_intuitiva",
    "explicacao_tecnica",
    "matematica",
    "logica_algoritmica",
    "python_iniciante",
    "perguntas_guia",
)


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        text = value
    elif isinstance(value, (int, float, bool)):
        text = str(value)
    else:
        return default
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _safe_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    return [value]


def _safe_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _clean_textual_output(text: str) -> str:
    cleaned = _safe_text(text)
    for marker in RAW_DICT_MARKERS:
        if marker in cleaned:
            return ""
    return cleaned


def _stringify_scalar_list(values: Iterable[Any]) -> List[str]:
    output: List[str] = []
    for item in values:
        if isinstance(item, (dict, list, tuple, set)):
            continue
        text = _safe_text(item)
        if text:
            output.append(text)
    return output


def carregar_base_pedagogica(path: Optional[Path] = None) -> Dict[str, Any]:
    arquivo = Path(path) if path else BASE_FILE
    conteudo = json.loads(arquivo.read_text(encoding="utf-8"))
    return normalizar_base_pedagogica(conteudo)


def normalizar_base_pedagogica(base: Dict[str, Any]) -> Dict[str, Any]:
    base_norm = _safe_dict(base)
    conceitos_norm: List[Dict[str, Any]] = []
    for raw in _safe_list(base_norm.get("conceitos")):
        item = _safe_dict(raw)
        conceito: Dict[str, Any] = {
            "id": _safe_text(item.get("id"), "conceito_sem_id"),
            "titulo": _safe_text(item.get("titulo"), "Conceito"),
            "categoria": _safe_text(item.get("categoria"), "geral"),
            "objetivo_didatico": _safe_text(item.get("objetivo_didatico")),
            "analogias": _stringify_scalar_list(_safe_list(item.get("analogias"))),
        }
        for key in REQUIRED_CONCEPT_KEYS:
            if key == "perguntas_guia":
                conceito[key] = _stringify_scalar_list(_safe_list(item.get(key)))
            else:
                conceito[key] = _clean_textual_output(item.get(key))
        conceitos_norm.append(conceito)

    base_norm["conceitos"] = conceitos_norm
    return base_norm


def indexar_conceitos(base: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {str(item.get("id") or ""): dict(item) for item in _safe_list(base.get("conceitos")) if item}


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


def _linhas_para_texto(linhas: Iterable[Dict[str, Any]]) -> List[str]:
    saida: List[str] = []
    for item in linhas:
        linha = _safe_dict(item)
        nome = _safe_text(linha.get("insumo_nome"))
        massa = _safe_float(linha.get("massa_kg"))
        if nome:
            saida.append(f"- {nome}: {massa:.3f} kg" if massa is not None else f"- {nome}")
    return saida


def selecionar_conceitos(snapshot: Dict[str, Any], base: Dict[str, Any]) -> List[str]:
    ids: List[str] = ["indice_saturacao", "carga_salina", "tiers"]

    pares = _stringify_scalar_list(_safe_list(snapshot.get("pares_criticos")))
    aditivos = _stringify_scalar_list(_safe_list(snapshot.get("aditivos_sugeridos")))
    ph = _safe_float(snapshot.get("ph_teorico"))
    ionic = _safe_float(snapshot.get("forca_ionica"))
    hlb = _safe_float(snapshot.get("hlb_requerido"))
    thermal = _safe_dict(snapshot.get("balanco_termico"))
    sat = _safe_float(snapshot.get("indice_saturacao"))
    modo_sc = bool(snapshot.get("modo_sc", False))

    if pares:
        ids.append("pares_kps")
    if ph is not None:
        ids.append("ph_teorico")
    if ionic is not None:
        ids.append("forca_ionica")
    if hlb is not None:
        ids.append("hlb")
    if any(_safe_float(v) is not None for v in thermal.values()):
        ids.append("balance_termico")
    if modo_sc or (sat is not None and sat > 1.10):
        ids.append("reologia")
    if aditivos:
        ids.append("aditivos")

    conceitos = indexar_conceitos(base)
    ordered: List[str] = []
    for cid in ids:
        if cid in conceitos and cid not in ordered:
            ordered.append(cid)
    return ordered


def construir_contexto_formula(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    snap = _safe_dict(snapshot)
    sat = _safe_float(snap.get("indice_saturacao"))
    carga = _safe_float(snap.get("carga_salina_pct_mv"))
    ph = _safe_float(snap.get("ph_teorico"))
    ionic = _safe_float(snap.get("forca_ionica"))
    thermal = _safe_dict(snap.get("balanco_termico"))

    linhas_norm: List[Dict[str, Any]] = []
    for item in _safe_list(snap.get("linhas")):
        linha = _safe_dict(item)
        linhas_norm.append(
            {
                "insumo_nome": _safe_text(linha.get("insumo_nome")),
                "massa_kg": _safe_float(linha.get("massa_kg")),
            }
        )

    contexto: Dict[str, Any] = {
        "nome_formula": _safe_text(snap.get("nome_formula"), "Fórmula sem nome"),
        "tier": _safe_text(snap.get("tier"), "N/D") or "N/D",
        "volume_l": _safe_float(snap.get("volume_l")),
        "temperatura_c": _safe_float(snap.get("temperatura_c")),
        "indice_saturacao": sat,
        "classe_saturacao": classificar_indice_saturacao(sat),
        "carga_salina_pct_mv": carga,
        "classe_carga_salina": classificar_carga_salina(carga),
        "ph_teorico": ph,
        "classe_ph": classificar_ph(ph),
        "forca_ionica": ionic,
        "classe_forca_ionica": classificar_forca_ionica(ionic),
        "pares_criticos": _stringify_scalar_list(_safe_list(snap.get("pares_criticos"))),
        "aditivos_sugeridos": _stringify_scalar_list(_safe_list(snap.get("aditivos_sugeridos"))),
        "linhas": linhas_norm,
        "balanco_termico": {
            "temp_entrada_c": _safe_float(thermal.get("temp_entrada_c")),
            "temp_saida_c": _safe_float(thermal.get("temp_saida_c")),
            "delta_t_c": _safe_float(thermal.get("delta_t_c")),
            "calor_total_kj": _safe_float(thermal.get("calor_total_kj")),
        },
        "hlb_requerido": _safe_float(snap.get("hlb_requerido")),
        "modo_sc": bool(snap.get("modo_sc", False)),
        "resumo_risco": _clean_textual_output(snap.get("resumo_risco")),
    }
    return contexto


def montar_fatos_dinamicos(conceito_id: str, contexto: Dict[str, Any]) -> List[str]:
    fatos: List[str] = []

    if conceito_id == "indice_saturacao":
        sat = contexto.get("indice_saturacao")
        classe = contexto.get("classe_saturacao")
        fatos.append(f"Índice de saturação calculado: {sat:.3f}." if isinstance(sat, float) else "Índice de saturação não informado.")
        fatos.append(f"Leitura operacional: {classe}.")
    elif conceito_id == "carga_salina":
        carga = contexto.get("carga_salina_pct_mv")
        classe = contexto.get("classe_carga_salina")
        fatos.append(f"Carga salina estimada: {carga:.2f}% m/v." if isinstance(carga, float) else "Carga salina não informada.")
        fatos.append(f"Leitura operacional: {classe}.")
    elif conceito_id == "pares_kps":
        pares = contexto.get("pares_criticos", [])
        fatos.append("Pares críticos detectados: " + ", ".join(pares) + "." if pares else "Nenhum par crítico foi informado.")
    elif conceito_id == "balance_termico":
        bt = _safe_dict(contexto.get("balanco_termico"))
        tin = bt.get("temp_entrada_c")
        tout = bt.get("temp_saida_c")
        dt = bt.get("delta_t_c")
        if any(isinstance(v, float) for v in (tin, tout, dt)):
            partes = []
            if isinstance(tin, float):
                partes.append(f"Entrada: {tin:.1f} °C")
            if isinstance(tout, float):
                partes.append(f"Saída estimada: {tout:.1f} °C")
            if isinstance(dt, float):
                partes.append(f"ΔT: {dt:.1f} °C")
            fatos.append(" | ".join(partes))
        else:
            fatos.append("Não há dados confiáveis de balanço térmico no snapshot.")
    elif conceito_id == "ph_teorico":
        ph = contexto.get("ph_teorico")
        classe = contexto.get("classe_ph")
        fatos.append(f"pH teórico estimado: {ph:.2f}." if isinstance(ph, float) else "pH teórico não informado.")
        fatos.append(f"Leitura operacional: {classe}.")
    elif conceito_id == "forca_ionica":
        ionic = contexto.get("forca_ionica")
        classe = contexto.get("classe_forca_ionica")
        fatos.append(f"Força iônica estimada: {ionic:.3f}." if isinstance(ionic, float) else "Força iônica não informada.")
        fatos.append(f"Leitura operacional: {classe}.")
    elif conceito_id == "hlb":
        hlb = contexto.get("hlb_requerido")
        fatos.append(f"HLB requerido estimado: {hlb:.2f}." if isinstance(hlb, float) else "HLB requerido não informado.")
    elif conceito_id == "reologia":
        fatos.append("A fórmula foi marcada como modo SC." if contexto.get("modo_sc") else "A fórmula não foi marcada como modo SC.")
    elif conceito_id == "aditivos":
        aditivos = contexto.get("aditivos_sugeridos", [])
        fatos.append("Aditivos sugeridos: " + ", ".join(aditivos) + "." if aditivos else "Não há aditivos sugeridos no snapshot.")
    elif conceito_id == "tiers":
        fatos.append(f"A fórmula foi classificada como Tier {contexto.get('tier', 'N/D')}.")

    return [f for f in (_clean_textual_output(fato) for fato in fatos) if f]


def renderizar_secao_pedagogica(conceito: Dict[str, Any], contexto: Dict[str, Any]) -> Dict[str, Any]:
    secao_dados = {
        "tipo": "pedagogico",
        "conceito_id": _safe_text(conceito.get("id")),
        "analogias": _stringify_scalar_list(conceito.get("analogias", [])),
        "fatos_dinamicos": montar_fatos_dinamicos(_safe_text(conceito.get("id")), contexto),
        "perguntas_guia": _stringify_scalar_list(conceito.get("perguntas_guia", [])),
    }
    return {
        "id": _safe_text(conceito.get("id")),
        "titulo": _safe_text(conceito.get("titulo"), "Conceito"),
        "explicacao_intuitiva": _clean_textual_output(conceito.get("explicacao_intuitiva")),
        "explicacao_tecnica": _clean_textual_output(conceito.get("explicacao_tecnica")),
        "matematica": _clean_textual_output(conceito.get("matematica")),
        "logica_algoritmica": _clean_textual_output(conceito.get("logica_algoritmica")),
        "python_iniciante": _clean_textual_output(conceito.get("python_iniciante")),
        "perguntas_guia": _stringify_scalar_list(conceito.get("perguntas_guia", [])),
        "fatos_dinamicos": secao_dados["fatos_dinamicos"],
        "dados": secao_dados,
    }


def explicar_formula(snapshot: Dict[str, Any], base: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    base_norm = normalizar_base_pedagogica(base or carregar_base_pedagogica())
    contexto = construir_contexto_formula(snapshot)
    conceitos = indexar_conceitos(base_norm)
    conceitos_ativos = selecionar_conceitos(contexto, base_norm)

    secoes: List[Dict[str, Any]] = []
    for conceito_id in conceitos_ativos:
        conceito = _safe_dict(conceitos.get(conceito_id))
        if conceito:
            secoes.append(renderizar_secao_pedagogica(conceito, contexto))

    resumo = [
        f"Fórmula: {contexto['nome_formula']}",
        f"Tier: {contexto['tier']}",
        f"Saturação: {contexto['classe_saturacao']}",
        f"Carga salina: {contexto['classe_carga_salina']}",
    ]
    if contexto.get("classe_ph") != "não informado":
        resumo.append(f"pH: {contexto['classe_ph']}")
    if contexto.get("resumo_risco"):
        resumo.append(contexto["resumo_risco"])

    return {
        "metadados": {
            "fonte_base": str(BASE_FILE.name),
            "nome_formula": contexto["nome_formula"],
        },
        "resumo_executivo": _stringify_scalar_list(resumo),
        "linhas_formula": _linhas_para_texto(contexto.get("linhas", [])),
        "secoes": secoes,
    }


def renderizar_texto_explicacao(snapshot: Dict[str, Any], base: Optional[Dict[str, Any]] = None) -> str:
    explicacao = explicar_formula(snapshot, base=base)
    linhas: List[str] = []

    linhas.append(f"EXPLICAÇÃO PEDAGÓGICA — {explicacao['metadados']['nome_formula']}")
    linhas.append("")
    linhas.append("Resumo executivo:")
    for item in explicacao.get("resumo_executivo", []):
        linhas.append(f"- {item}")

    if explicacao.get("linhas_formula"):
        linhas.append("")
        linhas.append("Composição informada:")
        linhas.extend(explicacao["linhas_formula"])

    for secao in explicacao.get("secoes", []):
        linhas.append("")
        linhas.append("=" * 72)
        linhas.append(_safe_text(secao.get("titulo"), "Conceito"))
        linhas.append("=" * 72)
        linhas.append("Química intuitiva:")
        linhas.append(_safe_text(secao.get("explicacao_intuitiva")))
        linhas.append("")
        linhas.append("Química técnica:")
        linhas.append(_safe_text(secao.get("explicacao_tecnica")))
        linhas.append("")
        linhas.append("Matemática:")
        linhas.append(_safe_text(secao.get("matematica")))
        linhas.append("")
        linhas.append("Lógica:")
        linhas.append(_safe_text(secao.get("logica_algoritmica")))
        linhas.append("")
        linhas.append("Python para iniciante:")
        linhas.append(_safe_text(secao.get("python_iniciante")))

        fatos = _stringify_scalar_list(secao.get("fatos_dinamicos", []))
        if fatos:
            linhas.append("")
            linhas.append("Fatos desta fórmula:")
            for fato in fatos:
                linhas.append(f"- {fato}")

        perguntas = _stringify_scalar_list(secao.get("perguntas_guia", []))
        if perguntas:
            linhas.append("")
            linhas.append("Perguntas-guia:")
            for pergunta in perguntas:
                linhas.append(f"- {pergunta}")

    texto = "\n".join(linhas).strip() + "\n"
    for marker in RAW_DICT_MARKERS:
        texto = texto.replace(marker, "")
    return texto


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
            {"insumo_nome": "Nitrato de cálcio", "massa_kg": 8.0},
        ],
        "balanco_termico": {
            "temp_entrada_c": 25.0,
            "temp_saida_c": 17.5,
            "delta_t_c": -7.5,
        },
        "modo_sc": False,
        "resumo_risco": "Fórmula operacional, mas com margem reduzida de estabilidade.",
    }
    print(renderizar_texto_explicacao(exemplo_snapshot))
