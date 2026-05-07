import sys
sys.stdout.reconfigure(encoding='utf-8')

estudo_part = '''


# ──────────────────────────────────────────────
#  Geração do Estudo Completo
# ──────────────────────────────────────────────

@dataclass
class SecaoEstudo:
    """Uma seção do estudo químico pedagógico."""
    titulo: str
    explicacao: str
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
        titulo=f"ESTUDO QUÍMICO — F{idx} (Tier {tier})",
        explicacao=(
            f"Formulação com {len(lines)} insumos e {massa_total:.3f} kg de sais para {volume_l:.0f} L.\\n\\n"
            f"Insumos: {nomes_insumos}\\n\\n"
            f"Índice de Saturação: {sat:.4f} — {'CRÍTICO' if sat >= 1.0 else 'ELEVADO' if sat >= 0.85 else 'OK'}\\n\\n"
            f"---\\n"
        ),
    )
    secoes.append(secao_header)

    # ─── 1. Índice de Saturação ───
    alerta_sat = None
    rec_sat = None
    if sat >= 1.0:
        alerta_sat = "ALERTA: A calda está SATURADA. Risco de cristalização em temperaturas abaixo de 15°C."
        rec_sat = "Recomenda-se: usar aditivo cristalizante, aquecer a calda a 60°C, ou reduzir a concentração."
    elif sat >= 0.85:
        alerta_sat = "ATENÇÃO: A calda está próxima da saturação. Monitorar em dias frios."
        rec_sat = "Recomenda-se: aditivo estabilizante ou aquecimento preventivo."
    elif sat >= 0.60:
        alerta_sat = "MARGEM DE SEGURANÇA REDUZIDA: Ainda OK, mas próximo do limite de alerta."

    dados_sat = gerar_grafico_saturacao_por_insumo(lines, insumos, volume_l)
    texto_sat_detalhe = ""
    for d in dados_sat["dados"]:
        texto_sat_detalhe += (
            f"• {d['insumo']}: {d['massa_kg']:.3f} kg — "
            f"Limite: {d['limite_kg']:.3f} kg → {d['contrib_pct_saturacao']:.1f}% do índice\\n"
        )

    if texto_sat_detalhe:
        texto_sat = CONCEITOS["indice_saturacao"]["explicacao"] + "\\n\\n---\\n\\nContribuição de cada insumo:\\n" + texto_sat_detalhe
    else:
        texto_sat = CONCEITOS["indice_saturacao"]["explicacao"]

    secoes.append(SecaoEstudo(
        titulo=CONCEITOS["indice_saturacao"]["titulo"],
        explicacao=texto_sat,
        dados=dados_sat,
        alerta=alerta_sat,
        recomendacao=rec_sat,
    ))

    # ─── 2. Carga Salina ───
    carga_pct = (massa_total / volume_l) * 100.0 if volume_l > 0 else 0.0
    alerta_carga = None
    rec_carga = None
    if carga_pct >= 45:
        alerta_carga = "CARGA SALINA ALTA! Risco de instabilidade e precipitação."
        rec_carga = "Reduzir concentração ou fracionar em duas aplicações."
    elif carga_pct >= 30:
        alerta_carga = "Carga salina moderada. Monitorar compatibilidade."
    elif carga_pct > 0:
        alerta_carga = "Carga salina baixa. Segura."

    secao_carga = SecaoEstudo(
        titulo=CONCEITOS["carga_salina"]["titulo"],
        explicacao=(
            CONCEITOS["carga_salina"]["explicacao"] + "\\n\\n---\\n\\n"
            f"Carga salina calculada: {carga_pct:.1f}% (m/v)\\n"
            f"Massa total de sais: {massa_total:.3f} kg\\n"
            f"Volume: {volume_l:.0f} L\\n"
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
                        f"Par detectado: {a} ({val_a:.3f}%) + {b} ({val_b:.3f}%)\\n"
                        f"   → Risco: {meta['risco']}\\n"
                        f"   → Solução: {meta['agente_quelante']} a {float(meta['dose_pct'])*100:.2f}%\\n\\n"
                    )

        if tem_quelante:
            alerta_kps = "Par crítico detectado, MAS AGENTE QUELANTE PRESENTE na fórmula. Risco mitigado."
        else:
            alerta_kps = "PAR CRÍTICO DETECTADO! Necessário adicionar agente quelante."
            rec_kps = f"Adicionar {meta['agente_quelante']} a {float(meta['dose_pct'])*100:.2f}% para sequestrar os íons e evitar precipitação."
    else:
        texto_pares = "Nenhum par crítico detectado. Compatibilidade química OK."

    secao_kps = SecaoEstudo(
        titulo=CONCEITOS["pares_kps"]["titulo"],
        explicacao=CONCEITOS["pares_kps"]["explicacao"] + "\\n\\n---\\n\\n" + texto_pares,
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
            f"TEMPERATURA FINAL ESTIMADA: {float(tout):.1f}°C (< 15°C)!\\n"
            "A carga endotérmica de ureia/ácido bórico pode causar cristalização por choque térmico."
        )
        rec_term = "AQUECIMENTO OBRIGATÓRIO: Elevar a calda para no mínimo 30°C antes de dissolver os sais."
    elif tout is not None and float(tout) < 20.0:
        alerta_term = f"Temperatura final estimada em {float(tout):.1f}°C. Próximo do limite de segurança."
        rec_term = "Monitorar temperatura. Se ambiente < 18°C, considerar aquecimento."

    texto_term = CONCEITOS["balance_termico"]["explicacao"] + "\\n\\n---\\n\\n"
    if dados_term["dados"]:
        texto_term += "Contribuição térmica por insumo:\\n"
        for d in dados_term["dados"]:
            sinal = "+" if d["calor_kj"] >= 0 else ""
            texto_term += f"  • {d['insumo']}: {d['massa_kg']:.3f} kg × {d['delta_h_kj_kg']:+.0f} kJ/kg = {sinal}{d['calor_kj']:.1f} kJ ({d['tipo']})\\n"

    if dados_term.get("resumo"):
        r = dados_term["resumo"]
        texto_term += f"\\nResumo térmico:\\n  T entrada: {r['temp_entrada_c']:.0f}°C → T saída: {r['temp_saida_c']:.1f}°C\\n  ΔT: {r['delta_t_c']:.1f}°C\\n  Calor total: {r['calor_total_kj']:.0f} kJ"
        if r.get("kcal_para_manter", 0) > 0:
            texto_term += f"\\n  Kcal para manter T: ~{r['kcal_para_manter']:.0f} kcal"

    secao_term = SecaoEstudo(
        titulo=CONCEITOS["balance_termico"]["titulo"],
        explicacao=texto_term,
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
            alerta_ph = "pH muito ácido! Risco de corrosão e incompatibilidade com tanques PEAD."
            rec_ph = "Neutralizar parcialmente com base (KOH/NaOH) ou ajustar a formulação."
        elif ph_est > 7.0:
            alerta_ph = "pH alcalino. Micronutrientes metálicos podem precipitar."
            rec_ph = "Abaixar pH para ≤ 5.5 antes de adicionar metais (Fe, Zn, Cu, Mn)."
        elif ph_est > 5.5:
            alerta_ph = "pH > 5.5. Atenção ao adicionar micronutrientes — podem precipitar."
            rec_ph = "Manter pH ≤ 5.5 durante a etapa de complexação/micronutrientes."
        else:
            alerta_ph = "pH dentro da faixa ideal para fertilizantes líquidos (3.0-5.5)."

    texto_ph = CONCEITOS["ph_teorico"]["explicacao"] + "\\n\\n---\\n\\n"
    if ph_est is not None:
        texto_ph += f"pH teórico estimado: {ph_est:.1f}\\n\\n"

        acidez_names = ["acido fosforico", "acido sulfurico", "acido nitrico", "acido bórico", "acido borico",
                        "fosfato monoamônico", "fosfato monoamonico", "map",
                        "fosfato diamônico", "fosfato diaminico", "dap",
                        "sulfato de amônio", "sulfato de amonio", "nitrato de amônio", "nitrato de amonio"]
        basicidade_names = ["hidróxido", "hidroxido", "monoetanolamina", "dietanolamina", "trietanolamina",
                           "koh", "naoh"]

        for l in lines:
            nm = _norm_text(l.insumo_nome or "")
            if any(a in nm for a in acidez_names):
                texto_ph += f"  • {l.insumo_nome}: contribui para ACIDEZ\\n"
            if any(b in nm for b in basicidade_names):
                texto_ph += f"  • {l.insumo_nome}: contribui para ALCALINIDADE\\n"

    secao_ph = SecaoEstudo(
        titulo=CONCEITOS["ph_teorico"]["titulo"],
        explicacao=texto_ph,
        alerta=alerta_ph,
        recomendacao=rec_ph,
    )
    secoes.append(secao_ph)

    # ─── 6. Força Iônica ───
    ionic = _estimate_ionic_strength(lines, volume_l, ph_est=ph_est)
    alerta_ionic = None
    if ionic > 2.0:
        alerta_ionic = "Força iônica muito alta! Risco de 'salting out' e desestabilização."
    elif ionic > 1.0:
        alerta_ionic = "Força iônica elevada. Pode afetar solubilidade e estabilidade."
    else:
        alerta_ionic = "Força iônica dentro do esperado para fertilizantes."

    secao_ionic = SecaoEstudo(
        titulo=CONCEITOS["forca_ionica"]["titulo"],
        explicacao=CONCEITOS["forca_ionica"]["explicacao"] + f"\\n\\n---\\n\\nForça iônica estimada: {ionic:.3f} mol/L\\n\\n{alerta_ionic}",
        alerta=alerta_ionic,
    )
    secoes.append(secao_ionic)

    # ─── 7. Perfil Reológico ───
    sc_mode = float(sat) > 1.10
    alerta_reo = None
    rec_reo = None
    if sc_mode:
        alerta_reo = "MODO SUSPENSÃO CONCENTRADA (SC): Comportamento Não-Newtoniano!"
        rec_reo = "Equipamento requerido: Dispersor High Shear (Disco Cowles) 1500-3000 RPM."

    secao_reo = SecaoEstudo(
        titulo=CONCEITOS["reologia"]["titulo"],
        explicacao=CONCEITOS["reologia"]["explicacao"] + f"\\n\\n---\\n\\nPerfil identificado: {'Não-Newtoniano (SC)' if sc_mode else 'Newtoniano (solução verdadeira)'}",
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
                f"• {a.nome} ({a.abreviatura or '-'})\\n"
                f"  Grupo: {a.grupo or '-'} | Função: {a.funcao_principal or '-'}\\n"
                f"  Dose recomendada: {sug.dose_recomendada_pct_texto} ({sug.dose_recomendada_massa_texto})\\n"
                f"  Motivo: {sug.motivo}\\n\\n"
            )
    else:
        texto_ad = "Nenhum aditivo recomendado para esta formulação."

    secao_ad = SecaoEstudo(
        titulo=CONCEITOS["aditivos"]["titulo"],
        explicacao=CONCEITOS["aditivos"]["explicacao"] + "\\n\\n---\\n\\nAditivos recomendados para esta fórmula:\\n" + texto_ad,
    )
    secoes.append(secao_ad)

    # ─── 9. Nutrientes vs Alvo ───
    dados_nutri = gerar_grafico_distribuicao_nutrientes(lines, targets)
    texto_nutri = "Comparação entre o alvo solicitado e o obtido:\\n\\n"
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
        texto_nutri += f"  • {d['nutriente']}: alvo={d['alvo_pct']:.3f}% → obtido={d['obtido_pct']:.3f}% [{status}]\\n"

    secao_nutri = SecaoEstudo(
        titulo="Distribuição de Nutrientes vs. Alvo",
        explicacao=texto_nutri,
        dados=dados_nutri,
    )
    secoes.append(secao_nutri)

    # ─── 10. Tier Explicação ───
    secao_tier = SecaoEstudo(
        titulo=CONCEITOS["tiers"]["titulo"],
        explicacao=CONCEITOS["tiers"]["explicacao"] + f"\\n\\n---\\n\\nEsta formulação é Tier {tier}.",
    )
    secoes.append(secao_tier)

    return secoes
'''

with open('D:\\GitHub\\Orion_Fert_TRAE\\estudo_quimico.py', 'a', encoding='utf-8') as f:
    f.write(estudo_part)
print('Estudo completo written')
