"""
Módulo de Estudo Químico Pedagógico — ORION AGROQUIM

Gera explicações detalhadas, gráficos e análise conceito-a-conceito
de cada formulação de fertilizante líquido.
"""

from __future__ import annotations
import math
import textwrap
from typing import Any, Dict, List, Optional, Sequence, Tuple
from dataclasses import dataclass

from motor import (
    FormulaLine,
    FormulaOutput,
    Insumo,
    AditivoSuggestion,
    _saturation_index_total,
    _thermal_balance_estimate,
    _estimate_ph_theoretical,
    _estimate_ionic_strength,
    _estimate_mix_time_min,
    _estimated_density,
    _estimate_evap_loss_kg,
    _kps_triggered_pairs,
    _calculate_required_hlb_from_lines,
    DELTA_H_SOL_KJ_PER_KG,
    KPS_PARES_PROIBIDOS,
    _norm_text,
    format_num,
    _solubility_limit_mass_kg,
    _totals_from_lines,
)


# ──────────────────────────────────────────────
#  Textos pedagógicos e explicativos
# ──────────────────────────────────────────────

CONCEITOS: Dict[str, Dict[str, str]] = {
    "indice_saturacao": {
        "titulo": "Índice de Saturação (Risco de Cristalização)",
        "explicacao": (
            "O índice de saturação é a soma da fração de cada sal em relação ao seu limite de solubilidade na água. "
            "Quando este índice ultrapassa 1.0 (100%), a calda está saturada e há risco de cristalização,\n"
            "especialmente em temperaturas baixas (inverno).\n\n"
            "Cada insumo possui um valor de solubilidade (g/L ou kg/L) que varia com a temperatura.\n"
            "O motor calcula: sat_index = Σ (massa_insumo_i / limite_solubilidade_i)\n\n"
            "• < 0.60 → Seguro, margem de segurança para variações de temperatura\n"
            "• 0.60 - 0.84 → Moderado, monitorar\n"
            "• 0.85 - 0.99 → Elevado, requer aditivo cristalizante\n"
            "• ≥ 1.00 → Crítico! Risco real de precipitação a frio"
        ),
    },
    "carga_salina": {
        "titulo": "Carga Salina (Massa de Sais / Volume)",
        "explicacao": (
            "A carga salina representa a concentração total de sais dissolvidos na calda.\n"
            "Quanto maior a carga, maior a força iônica e maior a interação entre íons,\n"
            "podendo levar à precipitação de sais insolúveis.\n\n"
            "• < 30% (m/v) → Baixa, segura para maioria das formulações\n"
            "• 30-45% (m/v) → Média, requer atenção com compatibilidade\n"
            "• > 45% (m/v) → Alta! Risco de instabilidade física e precipitação"
        ),
    },
    "pares_kps": {
        "titulo": "Pares Críticos (KPS — Produto de Solubilidade)",
        "explicacao": (
            "Certos pares iônicos formam compostos insolúveis quando combinados em água.\n"
            "O motor detecta automaticamente estes pares e recomenda agentes quelantes para\n"
            "sequestrar os íons problemáticos e mantê-los em solução.\n\n"
            "Pares monitorados:\n"
            "• Ca²⁺ + SO₄²⁻ → Gesso (CaSO₄·2H₂O) — precipitado branco que entope bicos\n"
            "• Ca²⁺ + PO₄³⁻ → Fosfato de cálcio — insolúvel em pH alcalino\n"
            "• Mg²⁺ + PO₄³⁻ → Fosfato de magnésio — similar ao anterior\n\n"
            "Solução: Adicionar agente quelante (EDTA, DTPA, HBED) que complexa os metais\n"
            "e impede a formação dos precipitados."
        ),
    },
    "balance_termico": {
        "titulo": "Balanço Térmico (ΔT da Solubilização)",
        "explicacao": (
            "A dissolução de sais em água pode ser endotérmica (absorve calor, esfria a calda)\n"
            "ou exotérmica (libera calor, aquece a calda).\n\n"
            "Ureia (NH₂CONH₂): ΔH = +258 kJ/kg — FORTE endotérmica\n"
            "  → Dissolução 'congela' a calda, pode cair para 5-10°C\n"
            "  → Solubilidade cai com temperatura → cristalização!\n\n"
            "Ácido Bórico (H₃BO₃): ΔH = +110 kJ/kg — endotérmica moderada\n\n"
            "Ácido Fosfórico (H₃PO₄): ΔH = -80 kJ/kg — exotérmica\n"
            "Ácido Sulfúrico (H₂SO₄): ΔH = -250 kJ/kg — FORTE exotérmica\n"
            "  → Libera calor, pode aquecer a calda perigosamente\n"
            "  → Requer adição LENTA com monitoramento de temperatura!\n\n"
            "O motor calcula a temperatura final estimada e, se < 15°C,\n"
            "recomenda AQUECIMENTO OBRIGATÓRIO antes da dissolução."
        ),
    },
    "ph_teorico": {
        "titulo": "pH Teórico Estimado",
        "explicacao": (
            "O pH da calda é estimado com base nos insumos presentes:\n\n"
            "• Ácidos fortes (H₃PO₄, H₂SO₄, HNO₃) → pH ácido (~2-4)\n"
            "• Sais de amônio (MAP, DAP, Sulfato de Amônio) → pH levemente ácido (~4-6)\n"
            "• Bases (KOH, NaOH, Etanolaminas) → pH alcalino (~8-10)\n"
            "• Ureia → pH neutro (~7)\n\n"
            "O pH influencia diretamente:\n"
            "  → Solubilidade dos micronutrientes (metais precipitam em pH > 5.5-6.0)\n"
            "  → Eficácia dos quelantes (cada um tem faixa ótima de pH)\n"
            "  → Compatibilidade com adjuvantes e tanque de aplicação"
        ),
    },
    "forca_ionica": {
        "titulo": "Força Iônica (μ)",
        "explicacao": (
            "A força iônica mede a concentração total de íons na solução.\n"
            "Quanto maior a força iônica, mais os íons interagem entre si,\n"
            "reduzindo a atividade efetiva de cada espécie.\n\n"
            "μ = ½ Σ (c_i × z_i²)\n\n"
            "Onde c_i = concentração molar, z_i = carga do íon\n\n"
            "Força iônica alta (> 1.0 mol/L) → Efeito 'salting out'\n"
            "  → Reduz a solubilidade de sais orgânicos\n"
            "  → Pode desestabilizar quelantes e dispersantes\n"
            "  → Aumenta viscosidade da calda"
        ),
    },
    "reologia": {
        "titulo": "Perfil Reológico (Newtoniano vs. Não-Newtoniano)",
        "explicacao": (
            "A reologia descreve como o fluido se deforma sob tensão:\n\n"
            "• Newtoniano: Viscosidade constante, independente da taxa de cisalhamento\n"
            "  → Típico de soluções verdadeiras (sais dissolvidos)\n"
            "  → Fácil de bombear e envasar\n\n"
            "• Não-Newtoniano (Pseudoplástico/Dilatante): Viscosidade varia com agitação\n"
            "  → Típico de suspensões concentradas (SC) com índice de saturação > 1.10\n"
            "  → Requer HIGH SHEAR (dispersor Cowles) para homogeneizar\n"
            "  → Maior energia de processo e atenção ao bombeamento"
        ),
    },
    "tiers": {
        "titulo": "Tiers de Formulação — Estratégia",
        "explicacao": (
            "O motor gera 12 formulações divididas em 3 tiers estratégicos:\n\n"
            "• TIER 1 (F1-F4): Conservador\n"
            "  → Menor custo, commodities (ureia, MAP, KCl)\n"
            "  → Tanque simples PEAD/Fibra, processo a frio\n"
            "  → Ideal para produção em larga escala de baixo custo\n\n"
            "• TIER 2 (F5-F8): Audacioso / Exploratório\n"
            "  → Mistura de commodities + fontes alternativas\n"
            "  → Tanque inox com agitação mecânica\n"
            "  → Pode usar aquecimento moderado\n\n"
            "• TIER 3 (F9-F12): Alquimia / Não Ortodoxo\n"
            "  → Fontes não convencionais, alta concentração\n"
            "  → Reator encamisado com controle térmico\n"
            "  → Pode atingir modo SC (suspensão concentrada)"
        ),
    },
    "aditivos": {
        "titulo": "Aditivos — Funções e Critérios de Seleção",
        "explicacao": (
            "O motor recomenda aditivos automaticamente com base na análise química:\n\n"
            "• Quelantes (EDTA, DTPA, HBED, EDDHA):\n"
            "  → Sequestram metais (Ca, Mg, Fe, Zn, Cu, Mn)\n"
            "  → Escolhidos conforme o metal e faixa de pH\n"
            "  → Dose calculada para equivalência molar\n\n"
            "• Cristalizantes / Estabilizantes:\n"
            "  → Quando índice de saturação > 0.85\n"
            "  → Inibem nucleação e crescimento de cristais\n\n"
            "• Dispersantes / Suspensores:\n"
            "  → Modo SC (saturação > 1.10)\n"
            "  → Mantêm partículas em suspensão estável\n\n"
            "• Antiespumantes:\n"
            "  → Alta carga de sais ou agitação intensa\n"
            "  → Evita formação de espuma no processo"
        ),
    },
}


# ──────────────────────────────────────────────
#  Gráficos (ASCII + descrições para UI)
# ──────────────────────────────────────────────

def gerar_grafico_saturacao_por_insumo(
    lines: Sequence[FormulaLine],
    insumos: Sequence[Insumo],
    volume_l: float,
) -> Dict[str, Any]:
    """Gera dados para gráfico de barras: contribuição de cada insumo na saturação."""
    by_name = {i.nome: i for i in insumos}
    dados: List[Dict[str, Any]] = []
    for l in lines:
        ins = by_name.get(l.insumo_nome)
        if not ins:
            continue
        lim = _solubility_limit_mass_kg(ins, volume_l)
        if lim is None or lim <= 0:
            continue
        contrib = max(0.0, float(l.massa_kg)) / float(lim) * 100.0
        if contrib > 1.0:
            dados.append({
                "insumo": l.insumo_nome,
                "massa_kg": float(l.massa_kg),
                "limite_kg": float(lim),
                "contrib_pct_saturacao": round(contrib, 1),
            })
    dados.sort(key=lambda x: x["contrib_pct_saturacao"], reverse=True)
    return {"tipo": "barras", "titulo": "Contribuição por Insumo na Saturação", "dados": dados}


def gerar_grafico_distribuicao_nutrientes(
    lines: Sequence[FormulaLine],
    targets: Dict[str, float],
) -> Dict[str, Any]:
    """Gera dados para gráfico de pizza/radar: distribuição de nutrientes vs alvo."""
    from collections import defaultdict
    totais: Dict[str, float] = defaultdict(float)
    for l in lines:
        for k, v in (l.contrib_pct or {}).items():
            totais[k] += float(v or 0.0)

    dados: List[Dict[str, Any]] = []
    nutrientes_label = {
        "N": "Nitrogênio (N)", "P2O5": "Fósforo (P₂O₅)", "K2O": "Potássio (K₂O)",
        "Ca": "Cálcio (Ca)", "Mg": "Magnésio (Mg)", "S": "Enxofre (S)",
        "B": "Boro (B)", "Zn": "Zinco (Zn)", "Fe": "Ferro (Fe)",
        "Mn": "Manganês (Mn)", "Cu": "Cobre (Cu)", "Mo": "Molibdênio (Mo)",
        "Co": "Cobalto (Co)", "Ni": "Níquel (Ni)", "Si": "Silício (Si)",
    }

    for k in sorted(set(list(targets.keys()) + list(totais.keys()))):
        if k in nutrientes_label:
            alvo = round(float(targets.get(k, 0.0) or 0.0), 3)
            obtido = round(float(totais.get(k, 0.0) or 0.0), 3)
            if alvo > 0 or obtido > 0:
                dados.append({
                    "nutriente": nutrientes_label.get(k, k),
                    "sigla": k,
                    "alvo_pct": alvo,
                    "obtido_pct": obtido,
                    "diferenca": round(obtido - alvo, 3),
                    "atingido_pct": round((obtido / alvo * 100) if alvo > 0 else (100 if obtido == 0 else 999), 1),
                })

    return {"tipo": "radar", "titulo": "Distribuição de Nutrientes vs. Alvo", "dados": dados}


def gerar_grafico_carga_termica(
    lines: Sequence[FormulaLine],
    insumos: Sequence[Insumo],
    volume_l: float,
    temp_c: float,
) -> Dict[str, Any]:
    """Gera dados para gráfico de contribuição térmica de cada insumo."""
    dados: List[Dict[str, Any]] = []
    for l in lines:
        if not l.insumo_nome:
            continue
        hit = None
        for key in DELTA_H_SOL_KJ_PER_KG:
            if key in _norm_text(l.insumo_nome or ""):
                hit = key
                break
        if not hit:
            continue
        dh = float(DELTA_H_SOL_KJ_PER_KG.get(hit, 0.0) or 0.0)
        q = float(max(0.0, l.massa_kg)) * dh
        dados.append({
            "insumo": l.insumo_nome,
            "massa_kg": float(l.massa_kg),
            "delta_h_kj_kg": dh,
            "calor_kj": round(q, 1),
            "tipo": "endotérmico" if dh > 0 else "exotérmico",
        })

    dados.sort(key=lambda x: abs(x["calor_kj"]), reverse=True)
    thermal = _thermal_balance_estimate(lines, insumos, volume_l, temp_c) or {}
    return {
        "tipo": "barras_duplas",
        "titulo": "Balanço Térmico por Insumo",
        "dados": dados,
        "resumo": {
            "temp_entrada_c": temp_c,
            "temp_saida_c": thermal.get("temp_out_c"),
            "delta_t_c": thermal.get("delta_t_c"),
            "calor_total_kj": round(float(thermal.get("q_kj", 0.0) or 0.0), 1),
            "kcal_para_manter": round(float(thermal.get("heat_kcal_to_hold", 0.0) or 0.0), 0),
        },
    }


# ──────────────────────────────────────────────
#  Geração do Estudo Completo
# ──────────────────────────────────────────────

@dataclass
class SecaoEstudo:
    """Uma seção do estudo químico pedagógico."""
    titulo: str
    quimica: str = ""
    matematica: str = ""
    logica: str = ""
    python: str = ""
    dados: Optional[Dict[str, Any]] = None
    alerta: Optional[str] = None
    recomendacao: Optional[str] = None


def gerar_estudo_completo(
    idx: int,
    output: FormulaOutput,
    insumos: Sequence[Insumo],
    targets: Dict[str, float],
    volume_l: float,
    temp_c: float,
) -> List[SecaoEstudo]:
    """
    Gera o estudo químico completo para uma formulação.
    Retorna lista de seções para renderização na UI.
    """
    lines = output.lines
    sat = float(output.indice_saturacao or 0.0)
    secoes: List[SecaoEstudo] = []

    # ─── Cabeçalho da Fórmula ───
    tier = 1 if 1 <= idx <= 4 else (2 if 5 <= idx <= 8 else 3)
    nomes_insumos = ", ".join(l.insumo_nome or "" for l in lines if l.insumo_nome)
    massa_total = sum(l.massa_kg for l in lines)
    secao_header = SecaoEstudo(
        titulo=f"📊 ESTUDO QUÍMICO — F{idx} (Tier {tier})",
        quimica=(
            f"Formulação com {len(lines)} insumos e {massa_total:.3f} kg de sais para {volume_l:.0f} L.\n\n"
            f"Insumos: {nomes_insumos}\n\n"
            f"Índice de Saturação: {sat:.4f} — {'⚠️ CRÍTICO' if sat >= 1.0 else '⚠️ ELEVADO' if sat >= 0.85 else '✅ OK'}\n\n"
            f"---\n"
        ),
    )
    secoes.append(secao_header)

    # ─── 1. Índice de Saturação (detectado / justificado) ───
    alerta_sat = None
    rec_sat = None
    if sat >= 1.0:
        alerta_sat = "⚠️ ALERTA: A calda está SATURADA. Risco de cristalização em temperaturas abaixo de 15°C."
        rec_sat = "Recomenda-se: usar aditivo cristalizante, aquecer a calda a 60°C, ou reduzir a concentração."
    elif sat >= 0.85:
        alerta_sat = "⚠️ ATENÇÃO: A calda está próxima da saturação. Monitorar em dias frios."
        rec_sat = "Recomenda-se: aditivo estabilizante ou aquecimento preventivo."
    elif sat >= 0.60:
        alerta_sat = "ℹ️ MARGEM DE SEGURANÇA REDUZIDA: Ainda OK, mas próximo do limite de alerta."

    # Análise por insumo
    dados_sat = gerar_grafico_saturacao_por_insumo(lines, insumos, volume_l)
    texto_sat_detalhe = ""
    for d in dados_sat["dados"]:
        texto_sat_detalhe += (
            f"• {d['insumo']}: {d['massa_kg']:.3f} kg — "
            f"Limite: {d['limite_kg']:.3f} kg → {d['contrib_pct_saturacao']:.1f}% do índice\n"
        )

    if texto_sat_detalhe:
        texto_sat = CONCEITOS["indice_saturacao"]["explicacao"] + "\n\n---\n\nContribuição de cada insumo:\n" + texto_sat_detalhe
    else:
        texto_sat = CONCEITOS["indice_saturacao"]["explicacao"]

    secoes.append(SecaoEstudo(
        titulo=CONCEITOS["indice_saturacao"]["titulo"],
        quimica=texto_sat,
        dados=dados_sat,
        alerta=alerta_sat,
        recomendacao=rec_sat,
    ))

    # ─── 2. Carga Salina ───
    carga_pct = (massa_total / volume_l) * 100.0 if volume_l > 0 else 0.0
    alerta_carga = None
    rec_carga = None
    if carga_pct >= 45:
        alerta_carga = "🔴 CARGA SALINA ALTA! Risco de instabilidade e precipitação."
        rec_carga = "Reduzir concentração ou fracionar em duas aplicações."
    elif carga_pct >= 30:
        alerta_carga = "🟡 Carga salina moderada. Monitorar compatibilidade."
    elif carga_pct > 0:
        alerta_carga = "🟢 Carga salina baixa. Segura."

    secao_carga = SecaoEstudo(
        titulo=CONCEITOS["carga_salina"]["titulo"],
        quimica=(
            CONCEITOS["carga_salina"]["explicacao"] + "\n\n---\n\n"
            f"Carga salina calculada: {carga_pct:.1f}% (m/v)\n"
            f"Massa total de sais: {massa_total:.3f} kg\n"
            f"Volume: {volume_l:.0f} L\n"
        ),
        dados={
            "tipo": "indicador",
            "titulo": "Carga Salina",
            "valor": round(carga_pct, 1),
            "unidade": "% (m/v)",
            "faixas": [
                {"limite": 30, "label": "Seguro", "cor": "verde"},
                {"limite": 45, "label": "Moderado", "cor": "amarelo"},
                {"limite": 999, "label": "Crítico", "cor": "vermelho"},
            ],
        },
        alerta=alerta_carga,
        recomendacao=rec_carga,
    )
    secoes.append(secao_carga)

    # ─── 3. Pares KPS ───
    totals = _totals_from_lines(lines)
    triggered_pairs = _kps_triggered_pairs(totals, targets)

    tem_quelante = any(
        any(key in (l.insumo_nome or "").lower() for key in ("edta", "hbed", "dtpa", "hedta", "nta", "eddha", "quelant"))
        for l in lines
    )
    alerta_kps = None
    rec_kps = None
    texto_pares = ""
    if triggered_pairs:
        for pair, meta in KPS_PARES_PROIBIDOS.items():
            a, b = pair
            if a in totals and b in totals:
                val_a = float(totals.get(a, 0.0) or 0.0)
                val_b = float(totals.get(b, 0.0) or 0.0)
                if val_a > 0 and val_b > 0:
                    texto_pares += (
                        f"⚠️ Par detectado: {a} ({val_a:.3f}%) + {b} ({val_b:.3f}%)\n"
                        f"   → Risco: {meta['risco']}\n"
                        f"   → Solução: {meta['agente_quelante']} a {float(meta['dose_pct'])*100:.2f}%\n\n"
                    )

        if tem_quelante:
            alerta_kps = "✅ Par crítico detectado, MAS AGENTE QUELANTE PRESENTE na fórmula. Risco mitigado."
        else:
            alerta_kps = "🔴 PAR CRÍTICO DETECTADO! Necessário adicionar agente quelante."
            rec_kps = f"Adicionar {meta['agente_quelante']} a {float(meta['dose_pct'])*100:.2f}% para sequestrar os íons e evitar precipitação."
    else:
        texto_pares = "✅ Nenhum par crítico detectado. Compatibilidade química OK."

    secao_kps = SecaoEstudo(
        titulo=CONCEITOS["pares_kps"]["titulo"],
        quimica=CONCEITOS["pares_kps"]["explicacao"] + "\n\n---\n\n" + texto_pares,
        matematica="Kps ≈ [Ca²⁺]·[SO₄²⁻] (e pares análogos). Quando o produto iônico excede o Kps do sal, ocorre precipitação.",
        logica=(
            "O motor soma as contribuições por nutriente (totals) e testa combinações críticas (Ca+SO4, Ca+P2O5, Mg+P2O5).\n"
            "Se ambos os nutrientes aparecem com valores relevantes, dispara o alerta e recomenda um quelante."
        ),
        python=(
            "totals = _totals_from_lines(lines)\n"
            "triggered = _kps_triggered_pairs(totals, targets)\n"
            "if triggered and not tem_quelante:\n"
            "    print('Adicionar quelante para mitigar precipitação')\n"
        ),
        alerta=alerta_kps,
        recomendacao=rec_kps,
    )
    secoes.append(secao_kps)

    # ─── 4. Balanço Térmico ───
    thermal = _thermal_balance_estimate(lines, insumos, volume_l, temp_c) or {}
    dados_term = gerar_grafico_carga_termica(lines, insumos, volume_l, temp_c)
    tout = thermal.get("temp_out_c")
    needs_heat = False
    if tout is not None and float(tout) < 15.0:
        needs_heat = True

    alerta_term = None
    rec_term = None
    if needs_heat:
        alerta_term = (
            f"🔴 TEMPERATURA FINAL ESTIMADA: {float(tout):.1f}°C (< 15°C)!\n"
            "A carga endotérmica de ureia/ácido bórico pode causar cristalização por choque térmico."
        )
        rec_term = "AQUECIMENTO OBRIGATÓRIO: Elevar a calda para no mínimo 30°C antes de dissolver os sais."
    elif tout is not None and float(tout) < 20.0:
        alerta_term = f"🟡 Temperatura final estimada em {float(tout):.1f}°C. Próximo do limite de segurança."
        rec_term = "Monitorar temperatura. Se ambiente < 18°C, considerar aquecimento."

    texto_term = CONCEITOS["balance_termico"]["explicacao"] + "\n\n---\n\n"
    texto_term += (
        "ANALOGIA (Café gelado vs. café quente):\n"
        "Imagine que você coloca açúcar num café bem quente: ele dissolve fácil.\n"
        "Agora pense em colocar a mesma quantidade num café gelado: demora mais e pode sobrar cristal no fundo.\n"
        "Em formulações, vários sais (especialmente ureia/ácido bórico) “roubam” calor da água ao dissolver.\n"
        "Se a calda esfria demais, a solubilidade cai e o sistema pode cristalizar mesmo que, no papel, estivesse perto do limite.\n\n"
    )
    if dados_term["dados"]:
        texto_term += "Contribuição térmica por insumo:\n"
        for d in dados_term["dados"]:
            sinal = "+" if d["calor_kj"] >= 0 else ""
            texto_term += f"  • {d['insumo']}: {d['massa_kg']:.3f} kg × {d['delta_h_kj_kg']:+.0f} kJ/kg = {sinal}{d['calor_kj']:.1f} kJ ({d['tipo']})\n"

    if dados_term.get("resumo"):
        r = dados_term["resumo"]
        texto_term += f"\nResumo térmico:\n  T entrada: {r['temp_entrada_c']:.0f}°C → T saída: {r['temp_saida_c']:.1f}°C\n  ΔT: {r['delta_t_c']:.1f}°C\n  Calor total: {r['calor_total_kj']:.0f} kJ"
        if r.get("kcal_para_manter", 0) > 0:
            texto_term += f"\n  Kcal para manter T: ~{r['kcal_para_manter']:.0f} kcal"

    secao_term = SecaoEstudo(
        titulo=CONCEITOS["balance_termico"]["titulo"],
        quimica=texto_term,
        matematica="ΔT ≈ Σ (mᵢ · ΔHₛₒₗ,ᵢ) / (m_total · Cp)",
        logica=(
            "O computador faz exatamente o que um engenheiro faria na prancheta:\n"
            "1) Para cada ingrediente, pega a massa (kg) e um ΔH de dissolução (kJ/kg) quando disponível.\n"
            "2) Soma tudo para obter o saldo de calor (kJ).\n"
            "3) Converte isso em queda (ou subida) de temperatura usando a massa total de calda e um Cp médio.\n"
            "4) Se a temperatura final estimada cair abaixo do limiar (ex.: 15°C), o processo deve mudar (pré-aquecimento)."
        ),
        python=(
            "saldo_kj = 0.0\n"
            "for l in lines:\n"
            "    nome = _norm_text(l.insumo_nome)\n"
            "    dh_kj_kg = float(DELTA_H_SOL_KJ_PER_KG.get(nome, 0.0))\n"
            "    massa = float(max(0.0, l.massa_kg))\n"
            "    saldo_kj += massa * dh_kj_kg  # + endo (esfria), - exo (aquece)\n"
            "\n"
            "thermal = _thermal_balance_estimate(lines, insumos, volume_l, temp_c)\n"
            "t_out = thermal.get('temp_out_c') if thermal else None\n"
            "if t_out is not None and float(t_out) < 15.0:\n"
            "    # Regra de processo: evitar choque térmico e cristalização\n"
            "    print('AQUECER: elevar calda para ~30°C antes de dissolver sais críticos')\n"
        ),
        dados=dados_term,
        alerta=alerta_term,
        recomendacao=rec_term,
    )
    secoes.append(secao_term)

    # ─── 5. pH Teórico ───
    ph_est = _estimate_ph_theoretical(lines, volume_l)
    alerta_ph = None
    rec_ph = None
    if ph_est is not None:
        if ph_est < 3.0:
            alerta_ph = "🔴 pH muito ácido! Risco de corrosão e incompatibilidade com tanques PEAD."
            rec_ph = "Neutralizar parcialmente com base (KOH/NaOH) ou ajustar a formulação."
        elif ph_est > 7.0:
            alerta_ph = "🟡 pH alcalino. Micronutrientes metálicos podem precipitar."
            rec_ph = "Abaixar pH para ≤ 5.5 antes de adicionar metais (Fe, Zn, Cu, Mn)."
        elif ph_est > 5.5:
            alerta_ph = "🟡 pH > 5.5. Atenção ao adicionar micronutrientes — podem precipitar."
            rec_ph = "Manter pH ≤ 5.5 durante a etapa de complexação/micronutrientes."
        else:
            alerta_ph = "🟢 pH dentro da faixa ideal para fertilizantes líquidos (3.0-5.5)."

    texto_ph = CONCEITOS["ph_teorico"]["explicacao"] + "\n\n---\n\n"
    if ph_est is not None:
        texto_ph += f"pH teórico estimado: {ph_est:.1f}\n\n"

        # Análise dos contribuintes de pH
        acidez_names = ["acido fosforico", "acido sulfurico", "acido nitrico", "acido bórico", "acido borico",
                        "fosfato monoamônico", "fosfato monoamonico", "map",
                        "fosfato diamônico", "fosfato diaminico", "dap",
                        "sulfato de amônio", "sulfato de amonio", "nitrato de amônio", "nitrato de amonio"]
        basicidade_names = ["hidróxido", "hidroxido", "monoetanolamina", "dietanolamina", "trietanolamina",
                           "koh", "naoh"]

        for l in lines:
            nm = _norm_text(l.insumo_nome or "")
            if any(a in nm for a in acidez_names):
                texto_ph += f"  • {l.insumo_nome}: contribui para ACIDEZ\n"
            if any(b in nm for b in basicidade_names):
                texto_ph += f"  • {l.insumo_nome}: contribui para ALCALINIDADE\n"

    secao_ph = SecaoEstudo(
        titulo=CONCEITOS["ph_teorico"]["titulo"],
        quimica=texto_ph,
        alerta=alerta_ph,
        recomendacao=rec_ph,
    )
    secoes.append(secao_ph)

    # ─── 6. Força Iônica ───
    ionic = _estimate_ionic_strength(lines, volume_l, ph_est=ph_est)
    alerta_ionic = None
    if ionic > 2.0:
        alerta_ionic = "🔴 Força iônica muito alta! Risco de 'salting out' e desestabilização."
    elif ionic > 1.0:
        alerta_ionic = "🟡 Força iônica elevada. Pode afetar solubilidade e estabilidade."
    else:
        alerta_ionic = "🟢 Força iônica dentro do esperado para fertilizantes."

    secao_ionic = SecaoEstudo(
        titulo=CONCEITOS["forca_ionica"]["titulo"],
        quimica=(
            CONCEITOS["forca_ionica"]["explicacao"]
            + "\n\nANALOGIA (Pista de dança lotada):\n"
            "Pense nas moléculas de água como pessoas numa pista de dança e nos íons como convidados que entram com “seguranças”.\n"
            "Quando a pista está vazia (baixa força iônica), cada partícula dispersa tem espaço e a água consegue “solvatar” tudo bem.\n"
            "Quando a pista fica lotada (alta força iônica), falta espaço: a água fica ocupada solvando íons e sobra menos “atenção”\n"
            "para estabilizar partículas e estruturas coloidais. O resultado pode ser “salting-out” (perda de solubilidade/estabilidade)\n"
            "e floculação/precipitação.\n\n"
            f"---\n\nForça iônica estimada: {ionic:.3f} mol/L\n\n{alerta_ionic}"
        ),
        matematica="μ = ½ Σ (cᵢ · zᵢ²)",
        logica=(
            "A força iônica pesa mais os íons multivalentes (z²).\n"
            "Então Ca²⁺ e SO₄²⁻ “contam” muito mais do que K⁺, por exemplo.\n"
            "A rotina estima concentrações efetivas e soma ½·c·z² para obter μ.\n"
            "Depois compara μ com faixas e emite alerta (risco de salting-out/instabilidade)."
        ),
        python=(
            "ph_est = _estimate_ph_theoretical(lines, volume_l)\n"
            "ionic = _estimate_ionic_strength(lines, volume_l, ph_est=ph_est)\n"
            "print('Força iônica (μ) estimada:', ionic)\n"
            "if ionic > 2.0:\n"
            "    print('ALERTA: alto risco de salting-out e instabilidade coloidal')\n"
            "elif ionic > 1.0:\n"
            "    print('ATENÇÃO: força iônica elevada; revisar ordem de adição e dispersão')\n"
        ),
        alerta=alerta_ionic,
    )
    secoes.append(secao_ionic)

    # ─── 6.1 HLB (quando há fase oleosa/solvente) ───
    req_hlb = _calculate_required_hlb_from_lines(lines)
    if req_hlb is not None:
        secao_hlb = SecaoEstudo(
            titulo="HLB (Equilíbrio Hidrofílico-Lipofílico) — Emulsão",
            quimica=(
                "Quando a formulação contém fase oleosa (óleos/solventes hidrocarbonetos), ela não forma uma solução verdadeira.\n"
                "Em vez disso, precisa formar uma emulsão estável (gotículas dispersas). O HLB é um número que indica o\n"
                "quanto um tensoativo/emulsificante é mais hidrofílico (alto HLB) ou mais lipofílico (baixo HLB).\n"
                "O motor estima um HLB requerido (rHLB) da fase oleosa para orientar a escolha de emulsificantes.\n\n"
                "ANALOGIA (O diplomata entre dois países):\n"
                "A água e o óleo são como dois países com línguas diferentes — não se misturam por si só.\n"
                "O emulsificante é o diplomata: uma “mão” conversa com a água (parte hidrofílica) e a outra conversa com o óleo\n"
                "(parte lipofílica). O rHLB é como a “língua” predominante do país óleo: se o diplomata falar a língua errada,\n"
                "a negociação falha e as gotículas coalescem (separam)."
            ),
            matematica="rHLB ≈ Σ (HLB_req,óleo · fração_mássica_do_óleo)",
            logica=(
                "1) Detecta componentes 'oleosos' pelo nome (óleo, mineral oil, isopar, parafínico...).\n"
                "2) Calcula o rHLB como média ponderada pela massa.\n"
                "3) Quanto mais perto o HLB do emulsificante estiver do rHLB, maior a chance de emulsão estável."
            ),
            python=(
                "req_hlb = _calculate_required_hlb_from_lines(lines)\n"
                "if req_hlb is not None:\n"
                "    print('HLB requerido estimado:', req_hlb)\n"
                "    # Em prática: escolher emulsificante (ou blend) com HLB ~ req_hlb\n"
            ),
            alerta=f"HLB requerido estimado: {format_num(float(req_hlb), 2)}",
        )
        secoes.append(secao_hlb)

    # ─── 7. Perfil Reológico ───
    sc_mode = float(sat) > 1.10
    alerta_reo = None
    rec_reo = None
    if sc_mode:
        alerta_reo = "🔴 MODO SUSPENSÃO CONCENTRADA (SC): Comportamento Não-Newtoniano!"
        rec_reo = "Equipamento requerido: Dispersor High Shear (Disco Cowles) 1500-3000 RPM."

    secao_reo = SecaoEstudo(
        titulo=CONCEITOS["reologia"]["titulo"],
        quimica=CONCEITOS["reologia"]["explicacao"] + f"\n\n---\n\nPerfil identificado: {'Não-Newtoniano (SC)' if sc_mode else 'Newtoniano (solução verdadeira)'}",
        alerta=alerta_reo,
        recomendacao=rec_reo,
    )
    secoes.append(secao_reo)

    # ─── 8. Aditivos Recomendados ───
    if output.aditivos_sugeridos:
        texto_ad = ""
        for sug in output.aditivos_sugeridos:
            a = sug.aditivo
            texto_ad += (
                f"• {a.nome} ({a.abreviatura or '-'})\n"
                f"  Grupo: {a.grupo or '-'} | Função: {a.funcao_principal or '-'}\n"
                f"  Dose recomendada: {sug.dose_recomendada_pct_texto} ({sug.dose_recomendada_massa_texto})\n"
                f"  Motivo: {sug.motivo}\n\n"
            )
    else:
        texto_ad = "Nenhum aditivo recomendado para esta formulação."

    secao_ad = SecaoEstudo(
        titulo=CONCEITOS["aditivos"]["titulo"],
        quimica=CONCEITOS["aditivos"]["explicacao"] + "\n\n---\n\nAditivos recomendados para esta fórmula:\n" + texto_ad,
    )
    secoes.append(secao_ad)

    # ─── 9. Nutrientes vs Alvo ───
    dados_nutri = gerar_grafico_distribuicao_nutrientes(lines, targets)
    texto_nutri = "Comparação entre o alvo solicitado e o obtido:\n\n"
    for d in dados_nutri["dados"]:
        atingido = d["atingido_pct"]
        if atingido >= 200:
            status = "SOBRENUTRIÇÃO (>200%)"
        elif atingido >= 110:
            status = "OK (>110% alvo)"
        elif atingido >= 90:
            status = "OK (dentro da faixa)"
        elif atingido >= 50:
            status = "ABAIXO (50-90% alvo)"
        elif atingido >= 1:
            status = "CRÍTICO (<50% alvo)"
        elif atingido == 0 and d["alvo_pct"] > 0:
            status = "AUSENTE! Nutriente não fornecido!"
        else:
            status = "N/A"
        texto_nutri += f"  • {d['nutriente']}: alvo={d['alvo_pct']:.3f}% → obtido={d['obtido_pct']:.3f}% [{status}]\n"

    secao_nutri = SecaoEstudo(
        titulo="Distribuição de Nutrientes vs. Alvo",
        quimica=texto_nutri,
        dados=dados_nutri,
    )
    secoes.append(secao_nutri)

    # ─── 10. Tier Explicação ───
    secao_tier = SecaoEstudo(
        titulo=CONCEITOS["tiers"]["titulo"],
        quimica=CONCEITOS["tiers"]["explicacao"] + f"\n\n---\n\nEsta formulação é Tier {tier}.",
    )
    secoes.append(secao_tier)

    return secoes
