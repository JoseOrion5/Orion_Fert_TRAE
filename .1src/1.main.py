from __future__ import annotations
from pathlib import Path
import sys
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

# Adiciona o diretório pai ao sys.path para importar o motor.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import flet as ft
from motor import (
    Insumo, FormulaLine, Aditivo, AditivoSuggestion, ThermoStatus, RelatorioOP, FormulaOutput,
    NUTRIENT_COLUMNS, DEFAULT_VOLUME_L,
    BLOCKED_INSUMO_PATTERNS, BLOCKED_OBS_LABELS,
    _safe_float,
    BASE_UNICA_FILE,
    load_insumos, load_aditivos, verificar_viabilidade_termodinamica,
    calcular_custo_industrial, gerar_relatorio_op, format_num,
    build_line_for_target, merge_lines, calcular_agua_qsp,
    recommend_process_and_aditivos, build_top12_outputs, diagnosticar_operacoes_unitarias, candidates_for
)

def _runtime_dir() -> Path:
    try:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
    except Exception:
        pass
    return Path(__file__).resolve().parents[1]

def _write_error_log(text: str) -> None:
    try:
        log_path = _runtime_dir() / "orionagroquim_error.log"
        log_path.write_text(text, encoding="utf-8", errors="replace")
    except Exception:
        pass

def parse_targets_from_fields(fields: Dict[str, ft.TextField]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for key, tf in fields.items():
        v = _safe_float(tf.value)
        if v is not None and v > 0:
            out[key] = v
    return out

def build_thermo_alert(status: ThermoStatus) -> ft.Container:
    tier_config = {
        1: {"color": ft.Colors.BLUE, "alert": "Tier 1 - Conservador (regras duras e rotas ortodoxas)"},
        2: {"color": ft.Colors.ORANGE, "alert": "Tier 2 - Audacioso (pode usar rotas menos ortodoxas)"},
        3: {"color": ft.Colors.PURPLE_ACCENT, "alert": "Tier 3 - Alquimia Industrial (rotas não ortodoxas + processo avançado)"}
    }
    config = tier_config.get(status.tech_tier, tier_config[1])
    main_color = ft.Colors.RED if status.is_supersaturado else config["color"]
    alert_text = f"⚠️ ALERTA DE PROCESSO: {config['alert']}"
    if status.tech_tier <= 1:
        detail = "Aplicando restrições técnicas conservadoras (split/compatibilidade quando aplicável)."
    else:
        detail = "Modo exploratório: a partir da 5ª forma o motor pode relaxar regras de split e buscar rotas menos ortodoxas."

    return ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.WARNING_AMBER if status.is_supersaturado else ft.Icons.INFO_OUTLINE, 
                    color=main_color, size=30),
            ft.VerticalDivider(width=10, color=ft.Colors.TRANSPARENT),
            ft.Column([
                ft.Text(alert_text, weight=ft.FontWeight.BOLD, color=main_color, size=14),
                ft.Text(f"{status.tech_instruction} | {detail}", color=ft.Colors.with_opacity(0.8, main_color), size=12, italic=True),
            ], spacing=2, expand=True)
        ], alignment=ft.MainAxisAlignment.START),
        bgcolor=ft.Colors.with_opacity(0.1, main_color),
        border=ft.border.all(1, ft.Colors.with_opacity(0.4, main_color)),
        border_radius=8,
        padding=15,
        margin=ft.margin.only(bottom=10)
    )

def build_data_table(lines: Sequence[FormulaLine], insumos_bd: Sequence[Insumo], volume_l: float, targets: Dict[str, float], supply_chain_mode: bool = False, *, page: Optional[ft.Page] = None) -> ft.Control:
    if not lines:
        return ft.Container(content=ft.Text("Sem linhas na formulação.", size=12), padding=10)

    bd_map = {i.nome: i for i in insumos_bd}
    
    selected_nutrients = [(k, label) for k, label in NUTRIENT_COLUMNS if (k in targets and (targets.get(k) or 0) > 0)]
    columns = [
        ft.DataColumn(ft.Text("Insumo", weight=ft.FontWeight.BOLD)),
        ft.DataColumn(ft.Text("Mass (kg)", weight=ft.FontWeight.BOLD), numeric=True),
        ft.DataColumn(ft.Text("Formula (%)", weight=ft.FontWeight.BOLD), numeric=True),
        ft.DataColumn(ft.Text("R$/kg", weight=ft.FontWeight.BOLD), numeric=True),
        ft.DataColumn(ft.Text("Custo Linha", weight=ft.FontWeight.BOLD), numeric=True),
    ]

    for _, label in selected_nutrients:
        columns.append(ft.DataColumn(ft.Text(label, weight=ft.FontWeight.BOLD), numeric=True))

    rows = []
    
    # Cálculos prévios
    agua_kg = calcular_agua_qsp(volume_l, lines, insumos_bd)
    total_massa_final = sum(l.massa_kg for l in lines) + agua_kg
    
    # 1. Linhas de Insumos
    for line in lines:
        pct_formula = (line.massa_kg / total_massa_final * 100) if total_massa_final > 0 else 0.0
        cells = [
            ft.DataCell(ft.Text(line.insumo_nome, size=12)),
            ft.DataCell(ft.Text(format_num(line.massa_kg, 3), size=12)),
            ft.DataCell(ft.Text(f"{format_num(pct_formula, 2)}%", size=12)),
            ft.DataCell(ft.Text(f"R$ {format_num(line.preco_unit, 2)}", size=12)),
            ft.DataCell(ft.Text(f"R$ {format_num(line.custo_linha, 2)}", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)),
        ]

        for k_id, _ in selected_nutrients:
            val = line.contrib_pct.get(k_id, 0.0)
            cells.append(ft.DataCell(ft.Text(format_num(val, 2) if val > 0 else "-", size=12)))
        
        rows.append(ft.DataRow(cells=cells))

    # 2. Linha de Água de Balanço
    pct_agua = (agua_kg / total_massa_final * 100) if total_massa_final > 0 else 0.0
    agua_cells = [
        ft.DataCell(ft.Text("Água de Balanço", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_200)),
        ft.DataCell(ft.Text(format_num(agua_kg, 2))),
        ft.DataCell(ft.Text(f"{format_num(pct_agua, 2)}%", size=12)),
        ft.DataCell(ft.Text("R$ 0,00", size=12)),
        ft.DataCell(ft.Text("R$ 0,00", size=12)),
    ]
    for _ in selected_nutrients:
        agua_cells.append(ft.DataCell(ft.Text("-")))
    
    rows.append(ft.DataRow(cells=agua_cells))

    datatable = ft.DataTable(
        columns=columns,
        rows=rows,
        vertical_lines=ft.border.BorderSide(1, ft.Colors.with_opacity(0.4, ft.Colors.WHITE)),
        horizontal_lines=ft.border.BorderSide(1, ft.Colors.with_opacity(0.4, ft.Colors.WHITE)),
        heading_row_color=ft.Colors.with_opacity(0.15, ft.Colors.WHITE),
        border=ft.border.all(1, ft.Colors.with_opacity(0.4, ft.Colors.WHITE)),
        border_radius=8,
    )

    zoom_label = ft.Text("Zoom da grade: 100%", size=12, color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE))
    zoom_slider = ft.Slider(min=50, max=150, divisions=100, value=100)
    table_wrapper = ft.Container(content=datatable, padding=5, scale=1.0)

    def set_zoom(value: float) -> None:
        v = float(value or 100.0)
        v = max(50.0, min(150.0, v))
        zoom_slider.value = v
        zoom_label.value = f"Zoom da grade: {int(round(v))}%"
        table_wrapper.scale = v / 100.0
        if page:
            page.update()

    def on_zoom_slider_change(e):
        set_zoom(e.control.value)

    def on_zoom_in(_):
        set_zoom((zoom_slider.value or 100.0) + 10.0)

    def on_zoom_out(_):
        set_zoom((zoom_slider.value or 100.0) - 10.0)

    zoom_slider.on_change = on_zoom_slider_change

    zoom_bar = ft.Row(
        [
            ft.Icon(ft.Icons.SEARCH, size=18, color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE)),
            zoom_label,
            ft.IconButton(ft.Icons.ZOOM_OUT, on_click=on_zoom_out),
            zoom_slider,
            ft.IconButton(ft.Icons.ZOOM_IN, on_click=on_zoom_in),
        ],
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    scroll_row = ft.Row([table_wrapper], scroll=ft.ScrollMode.ALWAYS, expand=True)

    return ft.Container(
        content=ft.Column(
            [
                zoom_bar,
                ft.Container(content=scroll_row, expand=True),
            ],
            spacing=6,
        ),
        margin=ft.Margin.only(top=10, bottom=10),
    )

def build_viability_card(lines: Sequence[FormulaLine], volume_l: float, tech_tier: int = 1, aditivos_cache: List[Aditivo] = [], status: Optional[ThermoStatus] = None) -> ft.Control:
    total_custo = calcular_custo_industrial(lines, volume_l, tech_tier, aditivos_cache)
    custo_por_litro = total_custo / volume_l if volume_l > 0 else 0.0
    total_massa = sum(l.massa_kg for l in lines)
    massa_local = sum(l.massa_kg for l in lines if l.is_local)
    indice_local = (massa_local / total_massa * 100) if total_massa > 0 else 100.0
    
    # Valores termodinâmicos para o cabeçalho
    agua = status.agua_balanco_kg if (status and status.agua_balanco_kg is not None) else 0.0
    dens = status.densidade_calculada if (status and status.densidade_calculada is not None) else 0.0

    return ft.Card(
        content=ft.Container(
            padding=15,
            content=ft.Column([
                ft.Row([
                    ft.Text("Viabilidade Industrial", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(
                        content=ft.Text(f"Tier {tech_tier}", size=10, weight=ft.FontWeight.BOLD),
                        bgcolor=ft.Colors.BLUE_900,
                        padding=ft.padding.symmetric(horizontal=8, vertical=2),
                        border_radius=10
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([
                    ft.Column([
                        ft.Text("Custo Final", size=12, color=ft.Colors.with_opacity(0.7, ft.Colors.WHITE)),
                        ft.Text(f"R$ {format_num(custo_por_litro, 3)}/L", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400),
                    ]),
                    ft.VerticalDivider(width=20),
                    ft.Column([
                        ft.Text("Balanço Hídrico", size=12, color=ft.Colors.with_opacity(0.7, ft.Colors.WHITE)),
                        ft.Text(f"{format_num(agua, 2)} kg", size=16, weight=ft.FontWeight.BOLD),
                    ]),
                    ft.VerticalDivider(width=20),
                    ft.Column([
                        ft.Text("Densidade", size=12, color=ft.Colors.with_opacity(0.7, ft.Colors.WHITE)),
                        ft.Text(f"{format_num(dens, 3)} kg/L", size=16, weight=ft.FontWeight.BOLD),
                    ]),
                ], spacing=10)
            ])
        ),
        elevation=4,
    )

def build_formula_header(lines: Sequence[FormulaLine], volume_l: float, tech_tier: int, aditivos_cache: Sequence[Aditivo]) -> ft.Control:
    total_custo = calcular_custo_industrial(lines, volume_l, tech_tier, list(aditivos_cache))
    custo_por_litro = total_custo / volume_l if volume_l > 0 else 0.0
    densidade = sum(line.massa_kg for line in lines) / volume_l if volume_l > 0 else 0.0
    return ft.Container(
        content=ft.Row(
            [
                ft.Text(f"Custo: R$ {format_num(custo_por_litro, 3)}/L", weight=ft.FontWeight.BOLD, size=14),
                ft.Text(f"Densidade aprox.: {format_num(densidade, 3)} kg/L", weight=ft.FontWeight.BOLD, size=14),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=ft.padding.symmetric(horizontal=6, vertical=8),
    )

def build_recommendations_view(process_steps: Sequence[str], aditivos: Sequence[AditivoSuggestion], lines: Sequence[FormulaLine] = [], instrucoes_producao: Sequence[str] = ()) -> ft.Control:
    process_controls = [ft.Text("Processo e mitigadores", size=14, weight=ft.FontWeight.BOLD)]
    for step in process_steps:
        step_control = ft.Row([ft.Text(f"- {step}", size=12, color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE), expand=True)], spacing=5)
        for l in lines:
            if l.insumo_nome in step:
                step_control.controls.insert(0, ft.Icon("location_on" if l.is_local else "directions_boat", color=ft.Colors.GREEN_400 if l.is_local else ft.Colors.ORANGE_400, size=14))
                break
        process_controls.append(step_control)

    prod_controls = [ft.Text("Roteiro de produção", size=14, weight=ft.FontWeight.BOLD)]
    for line in instrucoes_producao:
        prod_controls.append(ft.Text(f"- {line}", size=12, color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE)))

    cards = []
    for s in aditivos:
        a = s.aditivo
        cards.append(ft.Container(
            content=ft.Column([
                ft.Text(f"{a.nome} ({a.abreviatura})" if a.abreviatura else a.nome, size=13, weight=ft.FontWeight.BOLD),
                ft.Text(s.motivo, size=12, color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE)),
                ft.Text(f"Dose: {s.dose_recomendada_pct_texto} ({s.dose_recomendada_massa_texto})", size=12),
            ], spacing=4),
            padding=10, border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)), border_radius=12,
        ))

    obs_controls = [ft.Text("Observações (fontes não incluídas)", size=14, weight=ft.FontWeight.BOLD)]
    obs_chips = [ft.Container(content=ft.Text(label, size=12), padding=ft.padding.symmetric(horizontal=10, vertical=6), border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)), border_radius=14) for label in BLOCKED_OBS_LABELS]

    return ft.Container(
        content=ft.Column(process_controls + [ft.Divider()] + prod_controls + [ft.Divider()] + [ft.Column(cards)] + [ft.Divider()] + [ft.Row(obs_chips, wrap=True)]),
        padding=10, border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)), border_radius=12,
    )

def _build_tabs_content(labels: Sequence[str], views: Sequence[ft.Control], scrollable: bool) -> ft.Control:
    tab_bar = ft.TabBar(tabs=[ft.Tab(label=label) for label in labels], scrollable=scrollable)
    tab_view = ft.TabBarView(controls=list(views), expand=True)
    return ft.Column([tab_bar, ft.Container(content=tab_view, expand=True)], expand=True)

def make_tabs(labels: Sequence[str], views: Sequence[ft.Control], selected_index: int = 0, scrollable: bool = True, expand: bool | int | None = None) -> ft.Tabs:
    return ft.Tabs(
        content=_build_tabs_content(labels, views, scrollable=scrollable),
        length=len(labels),
        selected_index=selected_index,
        expand=expand
    )

def set_tabs(tabs_control: ft.Tabs, labels: Sequence[str], views: Sequence[ft.Control], selected_index: int = 0, scrollable: bool = True) -> None:
    tabs_control.length = len(labels)
    tabs_control.selected_index = selected_index
    tabs_control.content = _build_tabs_content(labels, views, scrollable=scrollable)

def _main_impl(page: ft.Page) -> None:
    page.title = "OrionAgroquim — Simulador Industrial"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20
    page.window_width = 1440
    page.window_height = 900

    # --- ESTADO GLOBAL ---
    insumos_cache: List[Insumo] = []
    aditivos_cache: List[Aditivo] = []
    manual_lines: List[FormulaLine] = []
    manual_selected_nutrients = {k: False for k, _ in NUTRIENT_COLUMNS}

    # --- COMPONENTES DE INTERFACE ---
    
    # Cabeçalho
    header = ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.GRAIN, size=32, color=ft.Colors.BLUE_400),
            ft.Text("OrionAgroquim — Simulador Industrial", size=18, weight=ft.FontWeight.BOLD),
        ], alignment=ft.MainAxisAlignment.START),
        padding=ft.padding.only(left=20, top=10, bottom=10)
    )

    # Configurações Globais (Alvos, Condições e Motor)
    volume_field = ft.TextField(label="Volume Q.S.P (L)", value=str(int(DEFAULT_VOLUME_L)), width=140, dense=True)
    temp_field = ft.TextField(label="Temperatura (°C)", value="25", width=140, dense=True)
    supply_chain_switch = ft.Checkbox(label="Modo Logística / Compras (Ativar Preços Cocamar/Produquímica)", value=False)
    
    # Flags de bibliotecas
    numpy_switch = ft.Switch(label="numpy (cálculo base)", value=True, scale=0.8)
    scipy_switch = ft.Switch(label="scipy (otimização)", value=False, scale=0.8)
    limite_diversificacao = 75.0
    limite_diversificacao_text = ft.Text("Limite de Concentração por Fonte (%): 75", size=12)

    def on_limite_diversificacao_change(e):
        nonlocal limite_diversificacao
        limite_diversificacao = float(e.control.value or 75.0)
        limite_diversificacao_text.value = f"Limite de Concentração por Fonte (%): {int(round(limite_diversificacao))}"
        page.update()

    limite_diversificacao_slider = ft.Slider(
        min=50,
        max=100,
        divisions=50,
        value=75,
        on_change=on_limite_diversificacao_change,
    )

    reactor_dd = ft.Dropdown(
        label="Reator disponível",
        width=360,
        dense=True,
        value="3",
        options=[
            ft.dropdown.Option("1", "Tanque PEAD/Fibra (frio)"),
            ft.dropdown.Option("2", "Tanque Inox (agitação mecânica)"),
            ft.dropdown.Option("3", "Reator Encamisado (alto torque/aquec.)"),
        ],
    )

    # Alvos Nutricionais
    targets_fields = {k: ft.TextField(label=f"{label} (%)", width=100, dense=True, text_size=12) for k, label in NUTRIENT_COLUMNS}
    
    # Grid de Nutrientes (3 colunas conforme imagem)
    nutrient_grid = ft.Column([
        ft.Row([targets_fields["N"], targets_fields["P2O5"], targets_fields["K2O"]], spacing=5),
        ft.Row([targets_fields["Ca"], targets_fields["Mg"], targets_fields["S"]], spacing=5),
        ft.Row([targets_fields["SO4"], targets_fields["B"], targets_fields["Zn"]], spacing=5),
        ft.Row([targets_fields["Cu"], targets_fields["Mn"], targets_fields["Mo"]], spacing=5),
        ft.Row([targets_fields["Fe"], targets_fields["Co"], targets_fields["Ni"]], spacing=5),
        ft.Row([targets_fields["Se"], targets_fields["Si"]], spacing=5),
    ], spacing=5)

    # Painel Principal de Resultados
    principal_thermo_alert = ft.Container()
    principal_viability_container = ft.Container()
    principal_table_container = ft.Container()
    principal_reco_container = ft.Container()

    calc_button = ft.ElevatedButton(
        "CALCULAR",
        style=ft.ButtonStyle(
            color=ft.Colors.BLACK,
            bgcolor=ft.Colors.CYAN_400,
            padding=20,
            shape=ft.RoundedRectangleBorder(radius=25)
        ),
        on_click=lambda e: on_calculate_principal(e)
    )

    data_status_text = ft.Text("", size=11, italic=True, color=ft.Colors.GREY_400)

    config_column = ft.Column([
        ft.Text("Alvos, Condições e Motor", size=18, weight=ft.FontWeight.BOLD),
        data_status_text,
        ft.Row([temp_field, volume_field], spacing=5),
        reactor_dd,
        ft.Text("Nutrientes-alvo (%)", weight=ft.FontWeight.BOLD, size=14),
        nutrient_grid,
        ft.Text("Flags de bibliotecas", weight=ft.FontWeight.BOLD, size=14),
        ft.Column([numpy_switch, scipy_switch], spacing=0),
        limite_diversificacao_text,
        limite_diversificacao_slider,
        ft.Container(calc_button, margin=ft.Margin(0, 10, 0, 0)),
    ], spacing=10, scroll=ft.ScrollMode.AUTO)

    # Abas do Top 12 (Serão atualizadas dinamicamente)
    top12_tabs = make_tabs(["Opção 1"], [ft.Container()], expand=True)

    # Componentes Manual
    manual_active_nutrient_dd = ft.Dropdown(label="Nutriente Ativo", width=200, dense=True)
    manual_insumo_dd = ft.Dropdown(label="Insumo Selecionado", width=400, dense=True)
    manual_target_tf = ft.TextField(label="Meta (%)", width=120, dense=True)
    manual_nutrient_chips = ft.Row(wrap=True, spacing=5)
    manual_table_container = ft.Container()
    manual_thermo_alert = ft.Container()
    manual_reco_container = ft.Container()

    # --- LÓGICA DE EVENTOS ---

    def get_volume() -> float: return _safe_float(volume_field.value) or DEFAULT_VOLUME_L
    def get_temp_c() -> float: return _safe_float(temp_field.value) or 25.0
    def get_reactor_level() -> int: return int(_safe_float(reactor_dd.value) or 3)

    def reload_data() -> None:
        nonlocal insumos_cache, aditivos_cache
        insumos_cache = load_insumos()
        aditivos_cache = load_aditivos()
        data_status_text.value = f"Fonte de dados: {BASE_UNICA_FILE.name} | Insumos carregados: {len(insumos_cache)}"
        update_manual_ui()

    def update_manual_ui() -> None:
        # Atualiza Chips de Nutrientes
        manual_nutrient_chips.controls = []
        for k, label in NUTRIENT_COLUMNS:
            def on_chip_click(e, nutrient_key=k):
                manual_selected_nutrients[nutrient_key] = e.control.selected
                update_manual_dropdowns()
                page.update()
            
            manual_nutrient_chips.controls.append(
                ft.Chip(
                    label=ft.Text(label, size=11),
                    selected=manual_selected_nutrients[k],
                    on_select=on_chip_click,
                    show_checkmark=True
                )
            )
        update_manual_dropdowns()

    def update_manual_dropdowns() -> None:
        manual_active_nutrient_dd.options = [
            ft.dropdown.Option(k) for k, v in manual_selected_nutrients.items() if v
        ]
        if manual_active_nutrient_dd.value not in [o.key for o in manual_active_nutrient_dd.options]:
            manual_active_nutrient_dd.value = None
        
        nut = manual_active_nutrient_dd.value
        if nut:
            cands = candidates_for(insumos_cache, nut)
            manual_insumo_dd.options = [ft.dropdown.Option(i.nome) for i in cands]
        else:
            manual_insumo_dd.options = []
        page.update()

    def add_manual_line(e):
        nut = manual_active_nutrient_dd.value
        ins_nome = manual_insumo_dd.value
        meta = _safe_float(manual_target_tf.value)
        if not (nut and ins_nome and meta): return
        
        ins = next((i for i in insumos_cache if i.nome == ins_nome), None)
        if not ins: return
        
        line = build_line_for_target(get_volume(), ins, nut, meta)
        if line:
            manual_lines.append(line)
            update_manual_table()

    def update_manual_table() -> None:
        merged = merge_lines(manual_lines)
        targets = {k: 1.0 for k, v in manual_selected_nutrients.items() if v}
        manual_table_container.content = build_data_table(merged, insumos_cache, get_volume(), targets, bool(supply_chain_switch.value), page=page)
        status = verificar_viabilidade_termodinamica(get_volume(), merged, insumos_cache)
        manual_thermo_alert.content = ft.Column([
            build_viability_card(merged, get_volume(), status.tech_tier, aditivos_cache, status),
            build_thermo_alert(status)
        ])
        
        steps, ad_sug = recommend_process_and_aditivos(
            {k: sum(l.contrib_pct.get(k, 0.0) for l in merged) for k, _ in NUTRIENT_COLUMNS},
            merged, aditivos_cache, insumos_cache, get_volume(), get_temp_c(),
            reactor_level_available=get_reactor_level()
        )
        instr = diagnosticar_operacoes_unitarias(merged, insumos_cache, ad_sug, get_volume(), get_temp_c())
        manual_reco_container.content = build_recommendations_view(steps, ad_sug, merged, instrucoes_producao=instr)
        page.update()

    def on_calculate_principal(e):
        try:
            reload_data()
            if not insumos_cache:
                page.snack_bar = ft.SnackBar(ft.Text("Erro ao carregar banco de dados!"))
                page.snack_bar.open = True
                page.update()
                return
                
            targets = parse_targets_from_fields(targets_fields)
            v = get_volume()
            # Conecta as flags da UI ao Motor
            use_opt = bool(scipy_switch.value)
            outputs = build_top12_outputs(
                v,
                targets,
                insumos_cache,
                aditivos_cache,
                get_temp_c(),
                use_optimization=use_opt,
                reactor_level_available=get_reactor_level(),
                limite_diversificacao=limite_diversificacao,
            )
            
            if not outputs or all(not o.lines for o in outputs):
                page.snack_bar = ft.SnackBar(ft.Text("Nenhuma formulação viável encontrada para os alvos informados!"))
                page.snack_bar.open = True
                page.update()
                return
                
            # Atualiza View Principal (Formulação 1)
            best = outputs[0] if outputs else FormulaOutput([], [], [], [], [], 0.0)
            status = verificar_viabilidade_termodinamica(v, best.lines, insumos_cache, 1)
            
            principal_thermo_alert.content = build_thermo_alert(status)
            principal_title_text.value = f"Formulação 1 (Tier {status.tech_tier})"
            principal_subtitle_text.value = f"Viabilizada em: {status.tech_instruction}"
            principal_viability_container.content = build_viability_card(best.lines, v, status.tech_tier, aditivos_cache, status)
            principal_table_container.content = build_data_table(best.lines, insumos_cache, v, targets, bool(supply_chain_switch.value), page=page)
            principal_reco_container.content = build_recommendations_view(best.process_steps, best.aditivos_sugeridos, best.lines, instrucoes_producao=best.instrucoes_producao)
            
            # Atualiza Abas Top 12
            build_top12_tabs(outputs)
            page.update()
        except Exception:
            import traceback
            err = traceback.format_exc()
            print(f"[ERRO CALCULAR]\n{err}", flush=True)
            _write_error_log(err)
            page.snack_bar = ft.SnackBar(ft.Text("Erro durante o cálculo. Verifique orionagroquim_error.log"))
            page.snack_bar.open = True
            page.update()

    # --- MONTAGEM DAS ABAS ---

    # Aba 1: Painel de Controle e Melhor Opção
    principal_title_text = ft.Text("Formulação 1", size=20, weight=ft.FontWeight.BOLD)
    principal_subtitle_text = ft.Text("Aguardando cálculo.", size=12, italic=True)
    tab_principal = ft.Row([
        # Coluna da Esquerda: Parâmetros
        ft.Container(
            content=config_column,
            width=360,
            padding=15,
            border=ft.Border.all(1, ft.Colors.GREY_800),
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE)
        ),
        
        # Coluna da Direita: Resultados
        ft.Column([
            principal_thermo_alert,
            principal_title_text,
            principal_subtitle_text,
            principal_viability_container,
            principal_table_container,
            ft.Divider(),
            ft.Container(
                content=ft.Column([
                    ft.Text("Processo e mitigadores", size=18, weight=ft.FontWeight.BOLD),
                    principal_reco_container
                ]),
                padding=10,
                border=ft.Border.all(1, ft.Colors.GREY_800),
                border_radius=10
            )
        ], expand=True, scroll=ft.ScrollMode.AUTO, spacing=5),
    ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START, spacing=20)

    # Aba 3: Formulação Manual
    tab_manual = ft.Column([
        ft.Card(ft.Container(padding=15, content=ft.Column([
            ft.Text("Configuração Manual", size=18, weight=ft.FontWeight.BOLD),
            manual_nutrient_chips,
            ft.Row([manual_active_nutrient_dd, manual_insumo_dd, manual_target_tf, 
                   ft.IconButton(ft.Icons.ADD_CIRCLE, icon_color=ft.Colors.GREEN_400, icon_size=32, on_click=add_manual_line)])
        ]))),
        manual_thermo_alert,
        manual_table_container,
        manual_reco_container
    ], scroll=ft.ScrollMode.AUTO)

    # Aba 4: Laudo (A4)
    laudo_content = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)

    app_tabs = make_tabs(
        ["PRINCIPAL", "TOP 5 FORMULAÇÕES", "FORMULAÇÃO MANUAL", "LAUDO"],
        [
            ft.Container(padding=20, content=tab_principal),
            ft.Container(padding=20, content=top12_tabs),
            ft.Container(padding=20, content=tab_manual),
            ft.Container(padding=20, content=laudo_content)
        ],
        selected_index=0,
        expand=True
    )

    # --- AUXILIARES DE RENDERIZAÇÃO ---

    def build_top12_formula_view(idx: int, output: FormulaOutput) -> ft.Control:
        try:
            v = get_volume()
            targets = parse_targets_from_fields(targets_fields)
            lines = output.lines
            status = verificar_viabilidade_termodinamica(v, lines, insumos_cache, idx)
            
            # Geração dos Componentes Individuais
            alerta_ui = build_thermo_alert(status)
            tabela_ui = build_data_table(lines, insumos_cache, v, targets, bool(supply_chain_switch.value), page=page)
            
            botao_laudo = ft.ElevatedButton(
                "ENVIAR PARA LAUDO / OP", 
                icon=ft.Icons.FILE_DOWNLOAD, 
                on_click=lambda _, l=lines, i=idx: on_send_to_laudo(l, i),
                style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_900, color=ft.Colors.WHITE)
            )
            
            recomendacoes_ui = build_recommendations_view(output.process_steps, output.aditivos_sugeridos, lines, instrucoes_producao=output.instrucoes_producao)
            
            # Agrupamento na Coluna Rolável
            conteudo_aba = ft.Container(
                content=ft.Column(
                    controls=[
                        alerta_ui, 
                        tabela_ui, 
                        botao_laudo,
                        recomendacoes_ui
                    ],
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                    spacing=5
                ),
                padding=10,
                expand=True
            )
            
            return conteudo_aba
            
        except Exception as e:
            import traceback
            print(f"Erro ao renderizar a fórmula {idx}: {e}")
            traceback.print_exc()
            return ft.Container(
                content=ft.Text(f"Erro na fórmula {idx}: {str(e)}", color=ft.Colors.RED_400, weight=ft.FontWeight.BOLD),
                padding=20
            )

    def build_top12_tabs(forms: List[FormulaOutput]) -> None:
        labels = []
        views = []
        
        for i, f in enumerate(forms):
            idx = i + 1
            # Determina o Tier e a cor
            if idx <= 4:
                label = f"F{idx} (Tier 1 - Conservador)"
                color = ft.Colors.BLUE_400
            elif idx <= 8:
                label = f"F{idx} (Tier 2 - Audacioso / exploratório)"
                color = ft.Colors.ORANGE_400
            else:
                label = f"F{idx} (Tier 3 - Alquimia / não ortodoxo)"
                color = ft.Colors.PURPLE_ACCENT
            
            labels.append(label)
            views.append(build_top12_formula_view(idx, f))
            
        set_tabs(top12_tabs, labels, views)
        page.update()

    def on_send_to_laudo(lines, idx):
        status = verificar_viabilidade_termodinamica(get_volume(), lines, insumos_cache, idx)
        rel = gerar_relatorio_op(lines, get_volume(), status)
        update_laudo_document(rel)
        app_tabs.selected_index = 3
        page.update()

    def update_laudo_document(rel: RelatorioOP):
        laudo_content.controls.clear()
        a4 = ft.Container(
            bgcolor=ft.Colors.WHITE, padding=50, width=800, border_radius=2,
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.BLACK54),
            content=ft.Column([
                ft.Row([
                    ft.Text("ORION AGROQUIM", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
                    ft.Column([
                        ft.Text(f"DATA: {rel.data_hora}", color=ft.Colors.BLACK, size=10),
                        ft.Text(f"TIER: {rel.tier}", color=ft.Colors.BLACK, size=10),
                    ], horizontal_alignment=ft.CrossAxisAlignment.END)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(color=ft.Colors.BLACK26),
                ft.Text(rel.titulo, size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900, text_align=ft.TextAlign.CENTER),
                ft.Text(f"Volume Final: {get_volume()} L | Densidade: {format_num(rel.densidade, 3)} | Balanço Hídrico: {format_num(rel.agua_balanco, 2)} kg", color=ft.Colors.BLACK87),
                ft.Text("\nCOMPOSIÇÃO DE CARGA (BOM)", weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
                ft.DataTable(
                    columns=[ft.DataColumn(ft.Text("Insumo", color=ft.Colors.BLACK)), ft.DataColumn(ft.Text("Massa (kg)", color=ft.Colors.BLACK))],
                    rows=[ft.DataRow([ft.DataCell(ft.Text(l.insumo_nome, color=ft.Colors.BLACK)), ft.DataCell(ft.Text(format_num(l.massa_kg, 3), color=ft.Colors.BLACK))]) for l in rel.bom_lines]
                ),
                ft.Text("\nPROCEDIMENTO OPERACIONAL (POP)", weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
                ft.Column([ft.Text(f"• {e['etapa']}: {e['procedimento']} ({e['notas']})", color=ft.Colors.BLACK87, size=12) for e in rel.pop_etapas]),
                ft.Text("\nPONTOS CRÍTICOS DE CONTROLE (PCC)", weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
                ft.Column([ft.Text(f"! {p['parametro']}: {p['limite']} -> {p['acao']}", color=ft.Colors.RED_900, size=11) for p in rel.pcc_pontos]),
            ])
        )
        laudo_content.controls.append(ft.Row([a4], alignment=ft.MainAxisAlignment.CENTER))
        page.update()

    page.add(header, app_tabs)
    reload_data()

def main(page: ft.Page) -> None:
    try:
        _main_impl(page)
    except Exception:
        import traceback
        err = traceback.format_exc()
        print(f"[ERRO FATAL]\n{err}", flush=True)
        _write_error_log(err)
        page.add(ft.Text("Erro fatal. Verifique orionagroquim_error.log"))

if __name__ == "__main__":
    ft.run(main)
