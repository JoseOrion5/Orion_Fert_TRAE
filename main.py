from __future__ import annotations
from pathlib import Path
import sys
import os
import tempfile
import math
import base64
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

# Adiciona o diretório pai ao sys.path para importar o motor.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import flet as ft
import estabilidade
import motor
<<<<<<< HEAD
=======
import estudo
import estudo_quimico_integrado as estudo_quimico
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
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

def _exports_dir() -> Path:
    path_str = r"C:\Users\orion\Documents\GitHub\Orion_Fert-NTB\Formulações e POP"
    exports_path = Path(path_str)
    exports_path.mkdir(parents=True, exist_ok=True)
    return exports_path

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
<<<<<<< HEAD
        border=ft.border.all(1, ft.Colors.with_opacity(0.4, main_color)),
=======
        border=ft.Border.all(1, ft.Colors.with_opacity(0.4, main_color)),
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
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
<<<<<<< HEAD
        border=ft.border.all(1, ft.Colors.with_opacity(0.4, ft.Colors.WHITE)),
=======
        border=ft.Border.all(1, ft.Colors.with_opacity(0.4, ft.Colors.WHITE)),
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
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

def build_recommendations_view(process_steps: Sequence[str], aditivos: Sequence[AditivoSuggestion], lines: Sequence[FormulaLine] = [], instrucoes_producao: Sequence[Any] = ()) -> ft.Control:
    process_controls = [ft.Text("Processo e mitigadores", size=14, weight=ft.FontWeight.BOLD)]
    for step in process_steps:
        step_control = ft.Row([ft.Text(f"- {step}", size=12, color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE), expand=True)], spacing=5)
        for l in lines:
            if l.insumo_nome in step:
                step_control.controls.insert(0, ft.Icon("location_on" if l.is_local else "directions_boat", color=ft.Colors.GREEN_400 if l.is_local else ft.Colors.ORANGE_400, size=14))
                break
        process_controls.append(step_control)

    prod_controls: List[ft.Control] = []
    if instrucoes_producao:
        prod_controls = [ft.Text("Roteiro de produção", size=14, weight=ft.FontWeight.BOLD)]
        for line in instrucoes_producao:
            if isinstance(line, dict):
                nm = str(line.get("nome_etapa") or "").strip()
                inst = str(line.get("instrucao_processo") or "").strip()
                text = f"{nm}: {inst}" if (nm and inst) else str(line)
                prod_controls.append(ft.Text(f"- {text}", size=12, color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE)))
            else:
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
<<<<<<< HEAD
            padding=10, border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)), border_radius=12,
        ))

    obs_controls = [ft.Text("Observações (fontes não incluídas)", size=14, weight=ft.FontWeight.BOLD)]
    obs_chips = [ft.Container(content=ft.Text(label, size=12), padding=ft.padding.symmetric(horizontal=10, vertical=6), border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)), border_radius=14) for label in BLOCKED_OBS_LABELS]
=======
            padding=10, border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)), border_radius=12,
        ))

    obs_controls = [ft.Text("Observações (fontes não incluídas)", size=14, weight=ft.FontWeight.BOLD)]
    obs_chips = [ft.Container(content=ft.Text(label, size=12), padding=ft.padding.symmetric(horizontal=10, vertical=6), border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)), border_radius=14) for label in BLOCKED_OBS_LABELS]
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c

    blocks: List[ft.Control] = []
    blocks.extend(process_controls)
    if prod_controls:
        blocks.extend([ft.Divider(), *prod_controls])
    blocks.extend([ft.Divider(), ft.Column(cards), ft.Divider(), ft.Row(obs_chips, wrap=True)])
    return ft.Container(
        content=ft.Column(blocks),
<<<<<<< HEAD
        padding=10, border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)), border_radius=12,
=======
        padding=10, border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)), border_radius=12,
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
    )


def build_production_roadmap(steps: Sequence[Dict[str, Any]]) -> ft.Control:
    header = ft.Text("📝 ROTEIRO DE PRODUÇÃO INDUSTRIAL", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)

    def _stage_colors(stage_name: str) -> Tuple[str, str]:
        s = (stage_name or "").casefold()
        if "prepar" in s or "matriz" in s:
            accent = ft.Colors.CYAN_400
        elif "complex" in s:
            accent = ft.Colors.PURPLE_400
        elif "dissol" in s or "satura" in s:
            accent = ft.Colors.ORANGE_400
        elif "micro" in s:
            accent = ft.Colors.TEAL_400
        elif "final" in s:
            accent = ft.Colors.GREEN_400
        else:
            accent = ft.Colors.BLUE_GREY_400
        bg = ft.Colors.with_opacity(0.12, accent)
        return accent, bg

    items: List[ft.Control] = []
    for i, s in enumerate(steps or [], start=1):
        nome = str(s.get("nome_etapa") or "").strip() or f"Etapa {i}"
        instr = str(s.get("instrucao_processo") or "").strip()
        tempo = str(s.get("tempo") or "").strip()

        pm = s.get("parametros_maquina") or {}
        equip = pm.get("equipamento")
        rpm = pm.get("rpm")
        rpm_faixa = pm.get("rpm_faixa")
        tc = pm.get("temp_c")

        gate = s.get("gate_ph") or {}
        gate_txt = str(gate.get("texto") or "").strip()

        pop_lines = s.get("pop") or []
        if not isinstance(pop_lines, list):
            pop_lines = []

        pccs = s.get("pccs") or []
        if not isinstance(pccs, list):
            pccs = []

        meta_bits = []
        if equip is not None and str(equip).strip():
            meta_bits.append(f"Equipamento: {equip}")
        if rpm_faixa is not None and str(rpm_faixa).strip():
            meta_bits.append(f"RPM (faixa): {rpm_faixa}")
        if rpm is not None and str(rpm).strip():
            meta_bits.append(f"RPM: {rpm}")
        if tc is not None and str(tc).strip():
            try:
                meta_bits.append(f"T: {float(tc):.1f}°C")
            except Exception:
                meta_bits.append(f"T: {tc}")
        if tempo:
            meta_bits.append(f"Tempo: {tempo}")
        meta = " | ".join(meta_bits)

        body_controls: List[ft.Control] = []
        if instr:
            body_controls.append(ft.Text(instr, size=12, color=ft.Colors.WHITE))
        if meta:
            body_controls.append(ft.Text(meta, size=11, color=ft.Colors.with_opacity(0.9, ft.Colors.WHITE)))
        if gate_txt:
            body_controls.append(ft.Text(gate_txt, size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400))

        if pop_lines:
            body_controls.append(ft.Text("POP:", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE))
            for ln in pop_lines[:5]:
                body_controls.append(ft.Text(f"- {ln}", size=11, color=ft.Colors.with_opacity(0.92, ft.Colors.WHITE)))

        if pccs:
            body_controls.append(ft.Text("PCC:", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE))
            for p in pccs[:6]:
                pid = str(p.get("id") or "").strip()
                par = str(p.get("parametro") or "").strip()
                lim = str(p.get("limite") or "").strip()
                acao = str(p.get("acao") or "").strip()
                txt = f"{pid} — {par}: {lim} → {acao}" if pid else f"{par}: {lim} → {acao}"
                body_controls.append(ft.Text(f"- {txt}", size=11, color=ft.Colors.with_opacity(0.92, ft.Colors.WHITE)))

        accent, bg = _stage_colors(nome)
        items.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Container(width=6, bgcolor=accent, border_radius=ft.border_radius.only(top_left=12, bottom_left=12)),
                        ft.Container(
                            expand=True,
                            content=ft.Column(
                                [
                                    ft.Text(f"{i}. {nome}", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                    *body_controls,
                                ],
                                spacing=4,
                            ),
<<<<<<< HEAD
                            padding=ft.padding.only(left=10, right=10, top=10, bottom=10),
=======
                            padding=ft.Padding.only(left=10, right=10, top=10, bottom=10),
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
                        ),
                    ],
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                bgcolor=bg,
<<<<<<< HEAD
                border=ft.border.all(1, ft.Colors.with_opacity(0.55, accent)),
=======
                border=ft.Border.all(1, ft.Colors.with_opacity(0.55, accent)),
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
                border_radius=12,
            )
        )

    if not items:
        items = [ft.Text("Sem roteiro disponível.", size=12, italic=True, color=ft.Colors.WHITE)]

    return ft.Container(
        content=ft.Column([header, ft.Divider()] + items, spacing=8),
        padding=10,
<<<<<<< HEAD
        border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
=======
        border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
        border_radius=12,
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
    TEMPLATE_INICIAL = {
        "N": "15.0",
        "P2O5": "10.0",
        "K2O": "20.0",
        "Ca": "2.0",
        "S": "2.5",
        "Fe": "0.5",
    }

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
    stability_module = estabilidade.StabilityModule(page=page)

    # --- COMPONENTES DE INTERFACE ---
    
    # Cabeçalho
    header = ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.GRAIN, size=32, color=ft.Colors.BLUE_400),
            ft.Text("OrionAgroquim — Simulador Industrial", size=18, weight=ft.FontWeight.BOLD),
        ], alignment=ft.MainAxisAlignment.START),
<<<<<<< HEAD
        padding=ft.padding.only(left=20, top=10, bottom=10)
=======
        padding=ft.Padding.only(left=20, top=10, bottom=10)
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
    )

    # Configurações Globais (Alvos, Condições e Motor)
    volume_field = ft.TextField(label="Volume Q.S.P (L)", value="100", width=140, dense=True)
    temp_field = ft.TextField(label="Temperatura (°C)", value="25", width=140, dense=True)
    supply_chain_switch = ft.Checkbox(label="Modo Logística / Compras (Ativar Preços Cocamar/Produquímica)", value=False)
    
    # Flags de bibliotecas
    numpy_switch = ft.Switch(label="numpy (cálculo base)", value=True, scale=0.8)
    scipy_switch = ft.Switch(label="scipy (otimização)", value=False, scale=0.8)
    anti_crystal_switch = ft.Checkbox(label="Anti-cristalização / Anti-sorvete", value=False)
    max_saturation_index = 1.0
    max_saturation_text = ft.Text("Índice de saturação máx: 1.00", size=12)
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

    def on_anti_crystal_change(e):
        nonlocal max_saturation_index
        max_saturation_index = 0.85 if bool(e.control.value) else 1.0
        max_saturation_text.value = f"Índice de saturação máx: {max_saturation_index:.2f}"
        page.update()

    anti_crystal_switch.on_change = on_anti_crystal_change

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
    targets_fields: Dict[str, ft.TextField] = {}
    for k, label in NUTRIENT_COLUMNS:
        targets_fields[k] = ft.TextField(
            label=f"{label} (%)",
            width=100,
            dense=True,
            text_size=12,
            value=TEMPLATE_INICIAL.get(k, ""),
        )
    
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

<<<<<<< HEAD
    calc_button = ft.ElevatedButton(
        "CALCULAR E VALIDAR",
=======
    calc_button = ft.Button(
        content="CALCULAR E VALIDAR",
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
        style=ft.ButtonStyle(
            color=ft.Colors.BLACK,
            bgcolor=ft.Colors.CYAN_400,
            padding=20,
            shape=ft.RoundedRectangleBorder(radius=25)
        ),
<<<<<<< HEAD
        on_click=lambda e: on_calculate_principal(e)
=======
        on_click=lambda e=None: on_calculate_principal(e)
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
    )

    reset_button = ft.OutlinedButton(
        "RESET",
        icon=ft.Icons.REFRESH,
<<<<<<< HEAD
        on_click=lambda e: on_reset_all(e),
=======
        on_click=lambda e=None: on_reset_all(e),
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
    )

    data_status_text = ft.Text("", size=11, italic=True, color=ft.Colors.GREY_400)
    progress_bar = ft.ProgressBar(width=360, color="cyan", visible=False)

    config_column = ft.Column([
        ft.Text("Alvos, Condições e Motor", size=18, weight=ft.FontWeight.BOLD),
        data_status_text,
        ft.Row([temp_field, volume_field], spacing=5),
        reactor_dd,
        ft.Text("Nutrientes-alvo (%)", weight=ft.FontWeight.BOLD, size=14),
        nutrient_grid,
        ft.Text("Flags de bibliotecas", weight=ft.FontWeight.BOLD, size=14),
        ft.Column([numpy_switch, scipy_switch], spacing=0),
        anti_crystal_switch,
        max_saturation_text,
        limite_diversificacao_text,
        limite_diversificacao_slider,
        progress_bar,
        ft.Row([calc_button, reset_button], spacing=10, wrap=True),
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
        status = verificar_viabilidade_termodinamica(get_volume(), merged, insumos_cache, temp_c=get_temp_c())
        manual_thermo_alert.content = ft.Column([
            build_viability_card(merged, get_volume(), status.tech_tier, aditivos_cache, status),
            build_thermo_alert(status)
        ])
        
        ph_est = motor._estimate_ph_theoretical(merged, get_volume())
        steps, ad_sug = recommend_process_and_aditivos(
            {k: sum(l.contrib_pct.get(k, 0.0) for l in merged) for k, _ in NUTRIENT_COLUMNS},
            merged, aditivos_cache, insumos_cache, get_volume(), get_temp_c(),
            ph_estimated=ph_est,
            reactor_level_available=get_reactor_level()
        )
        instr = diagnosticar_operacoes_unitarias(merged, insumos_cache, ad_sug, get_volume(), get_temp_c())
        manual_reco_container.content = build_recommendations_view(steps, ad_sug, merged, instrucoes_producao=instr)
        page.update()

    def on_calculate_principal(e):
        progress_bar.visible = True
        data_status_text.value = "Calculando as 12 variantes e roteiros... por favor, aguarde."
        calc_button.disabled = True
        page.update()

        def _do_calc() -> None:
            try:
                reload_data()
                data_status_text.value = "Calculando as 12 variantes e roteiros... por favor, aguarde."
                page.update()

                if not insumos_cache:
                    page.snack_bar = ft.SnackBar(ft.Text("Erro ao carregar banco de dados!"))
                    page.snack_bar.open = True
                    return

                targets = parse_targets_from_fields(targets_fields)
                v = get_volume()
                use_opt = bool(scipy_switch.value) or bool(anti_crystal_switch.value)
                outputs = build_top12_outputs(
                    v,
                    targets,
                    insumos_cache,
                    aditivos_cache,
                    get_temp_c(),
                    use_optimization=use_opt,
                    reactor_level_available=get_reactor_level(),
                    limite_diversificacao=limite_diversificacao,
                    max_saturation_index=max_saturation_index,
                )

                if not outputs or all(not o.lines for o in outputs):
                    page.snack_bar = ft.SnackBar(ft.Text("Nenhuma formulação viável encontrada para os alvos informados!"))
                    page.snack_bar.open = True
                    return

                best = outputs[0] if outputs else FormulaOutput([], [], [], [], [], 0.0)
                status = verificar_viabilidade_termodinamica(v, best.lines, insumos_cache, 1, temp_c=get_temp_c())

                principal_thermo_alert.content = build_thermo_alert(status)
                principal_title_text.value = f"Formulação 1 (Tier {status.tech_tier})"
                principal_subtitle_text.value = f"Viabilizada em: {status.tech_instruction}"
                principal_viability_container.content = build_viability_card(best.lines, v, status.tech_tier, aditivos_cache, status)
                principal_table_container.content = build_data_table(best.lines, insumos_cache, v, targets, bool(supply_chain_switch.value), page=page)
                principal_reco_container.content = build_recommendations_view(best.process_steps, best.aditivos_sugeridos, best.lines, instrucoes_producao=best.instrucoes_producao)

                build_top12_tabs(outputs)

                payload = {
                    "kind": "calc_run",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "volume_l": float(v),
                    "temp_c": float(_safe_float(temp_field.value) or 0.0),
                    "targets": dict(targets),
                    "outputs": [
                        {
                            "idx": i + 1,
                            "indice_saturacao": float(o.indice_saturacao or 0.0),
                            "lines": [
                                {"insumo_nome": l.insumo_nome, "massa_kg": float(l.massa_kg), "contrib_pct": dict(l.contrib_pct)}
                                for l in (o.lines or [])
                            ],
                            "process_steps": list(o.process_steps or []),
                            "instrucoes_producao": list(o.instrucoes_producao or []),
                            "aditivos_sugeridos": [
                                {
                                    "nome": s.aditivo.nome,
                                    "abreviatura": s.aditivo.abreviatura,
                                    "grupo": s.aditivo.grupo,
                                    "funcao_principal": s.aditivo.funcao_principal,
                                    "dose_recomendada_pct_texto": s.dose_recomendada_pct_texto,
                                    "dose_maxima_in39_pct_texto": s.dose_maxima_in39_pct_texto,
                                    "dose_recomendada_massa_texto": s.dose_recomendada_massa_texto,
                                    "motivo": s.motivo,
                                }
                                for s in (o.aditivos_sugeridos or [])
                            ],
                        }
                        for i, o in enumerate(outputs)
                    ],
                }
                ack = stability_module.ingest_calc_results(payload)
                if not ack.ok:
                    page.snack_bar = ft.SnackBar(ft.Text(f"Estabilidade: falha ao receber resultados ({ack.message})"))
                    page.snack_bar.open = True
                else:
                    if stability_module.last_has_alerts():
                        main_tabs.selected_index = 1
            except Exception:
                import traceback
                err = traceback.format_exc()
                print(f"[ERRO CALCULAR]\n{err}", flush=True)
                _write_error_log(err)
                page.snack_bar = ft.SnackBar(ft.Text("Erro durante o cálculo. Verifique orionagroquim_error.log"))
                page.snack_bar.open = True
            finally:
                progress_bar.visible = False
                calc_button.disabled = False
                data_status_text.value = f"Fonte de dados: {BASE_UNICA_FILE.name} | Insumos carregados: {len(insumos_cache)}"
                page.update()

        page.run_thread(_do_calc)

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

    calc_tabs = make_tabs(
        ["PRINCIPAL", "TOP 5 FORMULAÇÕES", "FORMULAÇÃO MANUAL"],
        [
            ft.Container(padding=20, content=tab_principal),
            ft.Container(padding=20, content=top12_tabs),
            ft.Container(padding=20, content=tab_manual),
        ],
        selected_index=0,
        expand=True
    )

    current_relatorio: Optional[RelatorioOP] = None
    report_history: List[Dict[str, Any]] = []

    report_history_list = ft.ListView(expand=True, spacing=4, auto_scroll=False)

    def _refresh_history_list() -> None:
        report_history_list.controls.clear()
        for item in reversed(report_history[-50:]):
            title = f"{item.get('data_hora','')} | {item.get('titulo','')}"
            subtitle = f"Tier {item.get('tier','')} | Volume {item.get('volume_l','')} L"
            report_history_list.controls.append(ft.ListTile(
                title=ft.Text(title, size=12, weight=ft.FontWeight.BOLD),
                subtitle=ft.Text(subtitle, size=11),
            ))
        page.update()

    def _serialize_relatorio(rel: RelatorioOP) -> Dict[str, Any]:
        return {
            "data_hora": rel.data_hora,
            "tier": rel.tier,
            "titulo": rel.titulo,
            "densidade": float(rel.densidade or 0.0),
            "agua_balanco": float(rel.agua_balanco or 0.0),
            "volume_l": float(get_volume()),
            "bom_lines": [{"insumo_nome": l.insumo_nome, "massa_kg": float(l.massa_kg)} for l in (rel.bom_lines or [])],
            "pop_etapas": list(rel.pop_etapas or []),
            "pcc_pontos": list(rel.pcc_pontos or []),
        }

    def _render_pdf(rel: RelatorioOP, out_path: Path, stability_snapshot: Optional[Dict[str, Any]]) -> None:
        def _extract_predicoes() -> Dict[str, Any]:
            for st in (rel.pop_etapas or []):
                if isinstance(st, dict):
                    p = st.get("predicoes")
                    if isinstance(p, dict):
                        return p
            return {}

        pred = _extract_predicoes()

        def _pred_line() -> str:
            if not pred:
                return ""
            phv = pred.get("ph_est")
            tout = pred.get("temp_out_c")
            dt = pred.get("delta_t_c")
            mixm = pred.get("mix_time_min")
            evapk = pred.get("evap_loss_kg")
            ionic = pred.get("ionic_strength")
            rheo = pred.get("reologia")
            bits = []
            if phv is not None:
                bits.append(f"pH teórico: {format_num(float(phv), 1)}")
            if tout is not None:
                bits.append(f"T final: {format_num(float(tout), 1)}°C")
            if dt is not None:
                bits.append(f"ΔT: {format_num(float(dt), 1)}°C")
            if mixm is not None and float(mixm) > 0:
                bits.append(f"Tempo mistura: {format_num(float(mixm), 0)} min")
            if evapk is not None and float(evapk) > 0:
                bits.append(f"Evap.: {format_num(float(evapk), 2)} kg")
            if ionic is not None and float(ionic) > 0:
                bits.append(f"I: {format_num(float(ionic), 3)}")
            if rheo:
                bits.append(f"Reologia: {str(rheo)}")
            return " | ".join(bits)

        pred_line = _pred_line()

        def _render_pdf_minimal(lines_txt: List[str]) -> None:
            out_path.parent.mkdir(parents=True, exist_ok=True)

            def esc(s: str) -> str:
                return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

            content_lines = [esc(str(x)) for x in (lines_txt or []) if str(x).strip()]
            if not content_lines:
                content_lines = ["Relatório vazio."]

            content = "BT\n/F1 10 Tf\n72 800 Td\n"
            for i, ln in enumerate(content_lines[:90]):
                if i:
                    content += "0 -14 Td\n"
                content += f"({ln}) Tj\n"
            content += "ET\n"
            stream = content.encode("latin-1", "replace")

            parts: List[bytes] = []
            offsets: List[int] = []

            def w(b: bytes) -> None:
                parts.append(b)

            w(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
            offsets.append(sum(len(p) for p in parts))
            w(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
            offsets.append(sum(len(p) for p in parts))
            w(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
            offsets.append(sum(len(p) for p in parts))
            w(b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n")
            offsets.append(sum(len(p) for p in parts))
            w(b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
            offsets.append(sum(len(p) for p in parts))
            w(f"5 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode("ascii"))
            w(stream)
            w(b"\nendstream\nendobj\n")

            xref_pos = sum(len(p) for p in parts)
            w(b"xref\n0 6\n0000000000 65535 f \n")
            for off in offsets:
                w(f"{off:010d} 00000 n \n".encode("ascii"))
            w(b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n")
            w(f"{xref_pos}\n".encode("ascii"))
            w(b"%%EOF\n")

            out_path.write_bytes(b"".join(parts))

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
        except ModuleNotFoundError:
            try:
                from fpdf import FPDF
                try:
                    from fpdf.enums import XPos, YPos
                except Exception:
                    class _XPos:
                        LMARGIN = "LMARGIN"
                        LEFT = "LEFT"
                        RIGHT = "RIGHT"

                    class _YPos:
                        NEXT = "NEXT"
                        TOP = "TOP"

                    XPos = _XPos
                    YPos = _YPos
            except ModuleNotFoundError:
                basic = [
                    "ORION AGROQUIM",
                    f"DATA: {rel.data_hora}",
                    f"TIER: {rel.tier}",
                    str(rel.titulo),
                    f"Volume Final: {get_volume()} L | Temperatura: {format_num(get_temp_c(), 1)}°C | Reator: {reactor_dd.value}",
                    f"Densidade: {format_num(rel.densidade, 3)} kg/L | Balanço Hídrico: {format_num(rel.agua_balanco, 2)} kg",
                ]
                if pred_line:
                    basic.append(pred_line)
                basic.append("")
                basic.append("COMPOSIÇÃO DE CARGA (BOM)")
                for l in (rel.bom_lines or []):
                    basic.append(f"- {l.insumo_nome}: {format_num(l.massa_kg, 3)} kg")
                _render_pdf_minimal(basic)
                return
            snap = stability_snapshot or {}
            ssum = (snap.get("summary") or {}) if isinstance(snap, dict) else {}
            lab = (snap.get("lab") or {}) if isinstance(snap, dict) else {}

            checklist_lines = [
                "[ ] Aparência homogênea (sem grumos/cristais visíveis)",
                "[ ] pH final registrado (alvo conforme TDS)",
                "[ ] Densidade registrada",
                "[ ] Filtrabilidade / bico ok (se aplicável)",
                "[ ] Amostra retida e identificada",
            ]

            tier = int(rel.tier or 1)
            if tier <= 1:
                sidebar_rgb = (30, 136, 229)
            else:
                sidebar_rgb = (123, 31, 162)

            class OrionPDF(FPDF):
                def header(self):
                    self.set_fill_color(*sidebar_rgb)
                    self.rect(0, 0, 5, float(self.h), style="F")
                    self.set_text_color(0, 0, 0)

            pdf = OrionPDF()
            pdf.set_margins(15, 15, 15)
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()

            page_width = float(pdf.w) - float(pdf.l_margin) - float(pdf.r_margin)

            def _sanitize_text(v: Any) -> str:
                s = str(v or "")
                s = s.replace("\t", " ")
                s = s.replace("•", "-")
                s = s.replace("→", "->")
                s = s.replace("↔", "<->")
                s = s.replace("⚠️", "")
                s = s.replace("⚠", "")
                s = s.replace("\r\n", "\n").replace("\r", "\n")
                return s

            using_unicode_font = False
            try:
                font_candidates = [
                    r"C:\Windows\Fonts\arial.ttf",
                    r"C:\Windows\Fonts\segoeui.ttf",
                    r"C:\Windows\Fonts\calibri.ttf",
                ]
                font_path = next((p for p in font_candidates if Path(p).exists()), None)
                if font_path:
                    pdf.add_font("OrionFont", "", font_path, uni=True)
                    pdf.add_font("OrionFont", "B", font_path, uni=True)
                    using_unicode_font = True
            except Exception:
                using_unicode_font = False
            pdf._orion_using_unicode = bool(using_unicode_font)

            def _safe_fpdf_text(v: Any) -> str:
                s = _sanitize_text(v)
                if using_unicode_font:
                    return s
                try:
                    return s.encode("latin-1", "replace").decode("latin-1")
                except Exception:
                    return s

            def set_font(size: int, *, bold: bool = False) -> None:
                if using_unicode_font:
                    pdf.set_font("OrionFont", style=("B" if bold else ""), size=size)
                else:
                    pdf.set_font("Helvetica", style=("B" if bold else ""), size=size)

            def draw_line(txt: Any) -> None:
                s = _safe_fpdf_text(txt).strip()
                if s:
                    pdf.multi_cell(0, 5, text=s, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                else:
                    pdf.ln(2)

            def _mm(val_mm: float) -> float:
                return float(val_mm)

            def _ensure_space(min_mm: float) -> None:
                remaining = float(pdf.h) - float(pdf.b_margin) - float(pdf.get_y())
                if remaining < _mm(min_mm):
                    pdf.add_page()

            def _draw_footer_last_page() -> None:
                footer_h = 30.0
                _ensure_space(footer_h)
                y = float(pdf.h) - float(pdf.b_margin) - footer_h
                pdf.set_xy(float(pdf.l_margin), y)
                set_font(8, bold=True)
                pdf.set_text_color(60, 60, 60)
                pdf.cell(0, 4.5, _safe_fpdf_text("CHECKLIST DE LIBERAÇÃO (A4)"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                set_font(8, bold=False)
                for ln in checklist_lines[:5]:
                    pdf.cell(0, 4.0, _safe_fpdf_text(ln), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(1)
                pdf.cell(0, 4.0, _safe_fpdf_text("Lote: ____________________   Data: ____/____/______   Responsável: ____________________"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.cell(0, 4.0, _safe_fpdf_text("Assinatura: _________________________________________________"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_text_color(0, 0, 0)

            def _is_gate_alert(text: str) -> bool:
                t = str(text or "").casefold()
                return ("não iniciar" in t) or ("alerta" in t) or ("ph >" in t)

            def _dissolution_lines(instr: str) -> List[str]:
                s = str(instr or "").strip()
                if ":" not in s:
                    return [s] if s else []
                head, tail = s.split(":", 1)
                items = [x.strip() for x in tail.split(",") if x.strip()]
                if not items:
                    return [s]
                out = [f"{head.strip()}:"]
                out.extend([f"  - {it}" for it in items])
                return out

            set_font(12, bold=True)
            y0 = pdf.get_y()
            left_w = page_width * 0.62
            right_w = page_width - left_w
            pdf.set_xy(pdf.l_margin, y0)
            pdf.cell(left_w, 6, _safe_fpdf_text("ORION AGROQUIM"), new_x=XPos.RIGHT, new_y=YPos.TOP, align="L")
            pdf.cell(right_w, 6, _safe_fpdf_text(f"DATA: {rel.data_hora}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
            set_font(10, bold=False)
            pdf.set_x(pdf.l_margin + left_w)
            pdf.cell(right_w, 5, _safe_fpdf_text(f"TIER: {rel.tier}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
            set_font(9, bold=False)
            set_font(11, bold=True)
            draw_line("")
            draw_line(str(rel.titulo))

            set_font(9, bold=False)
            draw_line(f"Volume Final: {get_volume()} L | Temperatura: {format_num(get_temp_c(), 1)}°C | Reator: {reactor_dd.value}")
            draw_line(f"Densidade: {format_num(rel.densidade, 3)} kg/L | Balanço Hídrico: {format_num(rel.agua_balanco, 2)} kg")
            if pred_line:
                draw_line(pred_line)

            risk_level = str(ssum.get("risk_level") or "").strip().lower()
            if risk_level == "vermelho":
                risk_rgb = (239, 83, 80)
                risk_label = "ALTO"
            elif risk_level == "amarelo":
                risk_rgb = (255, 202, 40)
                risk_label = "ATENÇÃO"
            elif risk_level == "verde":
                risk_rgb = (102, 187, 106)
                risk_label = "OK"
            else:
                risk_rgb = (189, 189, 189)
                risk_label = "N/D"

            pdf.ln(2)
            set_font(10, bold=True)
            pdf.set_fill_color(245, 245, 245)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(page_width * 0.55, 7, _safe_fpdf_text("ESTABILIDADE (RESUMO)"), border=1, ln=0, fill=True)
            pdf.set_fill_color(*risk_rgb)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(page_width * 0.45, 7, _safe_fpdf_text(f"RISCO: {risk_label}"), border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
            pdf.set_text_color(0, 0, 0)

            if ssum:
                sat = ssum.get("best_indice_saturacao")
                sal = ssum.get("best_carga_sais_pct_mv")
                txt = []
                if sat is not None:
                    txt.append(f"Sat: {format_num(float(sat), 3)}")
                if sal is not None:
                    txt.append(f"Sal: {format_num(float(sal), 1)}% (m/v)")
                rr = ssum.get("risk_reasons") or []
                if rr:
                    txt.append(f"Motivo: {str(rr[0])}")
                if txt:
                    set_font(9, bold=False)
                    pdf.multi_cell(0, 5, _safe_fpdf_text(" | ".join(txt)), border="LRB", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            if lab:
                set_font(9, bold=True)
                draw_line("BANCADA")
                set_font(9, bold=False)
                draw_line(f"pH: {lab.get('ph')} | EC (mS/cm): {lab.get('ec')} | Turbidez (NTU): {lab.get('turbidez')}")
                obs = str(lab.get("observacoes") or "").strip()
                if obs:
                    draw_line(f"Observações: {obs}")

            targets = parse_targets_from_fields(targets_fields)
            pdf.ln(6)
            set_font(10, bold=True)
            draw_line("ALVOS (TÍTULO)")
            set_font(9, bold=False)
            for k, label in NUTRIENT_COLUMNS:
                tv = float(targets.get(k, 0.0) or 0.0)
                if tv > 0:
                    draw_line(f"- {label}: {tv:.3f}%")

            pdf.ln(6)
            set_font(10, bold=True)
            draw_line("COMPOSIÇÃO DE CARGA (BOM)")

            col1 = page_width * 0.75
            col2 = page_width - col1
            pdf.set_fill_color(238, 238, 238)
            pdf.set_text_color(0, 0, 0)
            set_font(9, bold=True)
            pdf.cell(col1, 7, _safe_fpdf_text("Insumo"), border=1, new_x=XPos.RIGHT, new_y=YPos.TOP, fill=True)
            pdf.cell(col2, 7, _safe_fpdf_text("Massa (kg)"), border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
            set_font(9, bold=False)

            def _wrap_lines(text: str, width: float) -> List[str]:
                words = str(text or "").split()
                if not words:
                    return [""]
                lines: List[str] = []
                cur = ""
                for w in words:
                    cand = f"{cur} {w}".strip()
                    if pdf.get_string_width(cand) <= width or not cur:
                        cur = cand
                    else:
                        lines.append(cur)
                        cur = w
                if cur:
                    lines.append(cur)
                return lines

            for idx, l in enumerate(rel.bom_lines or []):
                fill = (idx % 2) == 1
                if fill:
                    pdf.set_fill_color(250, 250, 250)
                else:
                    pdf.set_fill_color(255, 255, 255)

                y = float(pdf.get_y())
                x = float(pdf.l_margin)
                insumo_lines = _wrap_lines(_safe_fpdf_text(l.insumo_nome), col1 - 4)
                row_h = max(6.0, float(len(insumo_lines)) * 5.0)
                _ensure_space(40.0)
                if float(pdf.h) - float(pdf.b_margin) - y < row_h:
                    pdf.add_page()
                    y = float(pdf.get_y())
                pdf.rect(x, y, col1, row_h)
                pdf.rect(x + col1, y, col2, row_h)
                pdf.set_xy(x + 2, y + 0.5)
                pdf.multi_cell(col1 - 4, 5, "\n".join(insumo_lines), border=0, new_x=XPos.LEFT, new_y=YPos.TOP)
                pdf.set_xy(x + col1, y)
                pdf.cell(col2, row_h, _safe_fpdf_text(f"{float(l.massa_kg):.3f}"), border=0, new_x=XPos.RIGHT, new_y=YPos.TOP, align="R")
                pdf.set_xy(x, y + row_h)

            def _draw_stage_box(stage_title: str, body_lines: List[str], *, tier: int) -> None:
                border_rgb = (33, 150, 243) if int(tier) <= 1 else (156, 39, 176)
                header_rgb = border_rgb
                x = pdf.l_margin
                w = page_width
                header_h = 7

                # Respiro antes de iniciar a nova caixa
                pdf.ln(5)
                _ensure_space(40.0)

                y_inicial = pdf.get_y()
                # Altura estática da caixa (estimativa base)
                box_h = header_h + 5 + (len(body_lines) * 5.5)

                if y_inicial + box_h > (pdf.h - pdf.b_margin):
                    pdf.add_page()
                    y_inicial = pdf.get_y()

                # 1. Desenha o Retângulo (Bordas)
                pdf.set_draw_color(*border_rgb)
                pdf.set_line_width(0.8)
                if hasattr(pdf, "rounded_rect"):
                    pdf.rounded_rect(x, y_inicial, w, box_h, 2.5)
                else:
                    pdf.rect(x, y_inicial, w, box_h)

                # 2. Desenha o Header (Título da Etapa)
                pdf.set_fill_color(*header_rgb)
                pdf.set_text_color(255, 255, 255)
                set_font(9, bold=True)
                pdf.set_xy(x, y_inicial)
                # Uso correto do fpdf2 moderno
                pdf.cell(w, header_h, _safe_fpdf_text(stage_title), border=0, new_x="LMARGIN", new_y="NEXT", fill=True)

                # 3. Escreve os Textos (Body)
                pdf.set_text_color(0, 0, 0)
                set_font(9, bold=False)
                pdf.set_xy(x + 2, y_inicial + header_h + 2) # Garante que o texto comece abaixo do header
                for ln in body_lines:
                    pdf.multi_cell(w - 4, 5, _safe_fpdf_text(ln), align="L", new_x="LMARGIN", new_y="NEXT")

                # 4. CORREÇÃO CRÍTICA DO OVERLAP (A MARRETA)
                # Pega a posição real onde o texto terminou
                y_apos_texto = pdf.get_y()
                y_final_caixa = y_inicial + box_h

                # O cursor deve ir para o MAIOR valor (fundo da caixa OU fim do texto) + margem de respiro
                y_seguro = max(y_final_caixa, y_apos_texto)

                # Seta o Y com 8 unidades de respiro ABNT para o próximo elemento
                pdf.set_y(y_seguro + 8)

            pop_etapas = list(rel.pop_etapas or [])
            pdf.ln(8)
            set_font(10, bold=True)
            if pop_etapas and isinstance(pop_etapas[0], dict) and ("nome_etapa" in pop_etapas[0]):
                pdf.ln(8)
                draw_line("ROTEIRO DE PRODUÇÃO INDUSTRIAL")
                for i, st in enumerate(pop_etapas, start=1):
                    nome = st.get("nome_etapa") or f"Etapa {i}"
                    instr = str(st.get("instrucao_processo") or "").strip()
                    tempo = str(st.get("tempo") or "").strip()
                    pm = st.get("parametros_maquina") or {}
                    rpm = pm.get("rpm")
                    tc = pm.get("temp_c")
                    gate = st.get("gate_ph") or {}
                    gate_txt = str(gate.get("texto") or "").strip()

                    body: List[str] = []
                    if instr:
                        if i == 3 or "dissol" in str(nome).casefold():
                            body.extend(_dissolution_lines(instr))
                        else:
                            body.append(instr)
                    meta_bits = []
                    if rpm is not None and str(rpm).strip():
                        meta_bits.append(f"RPM: {rpm}")
                    if tc is not None and str(tc).strip():
                        meta_bits.append(f"Temperatura: {tc}")
                    if tempo:
                        meta_bits.append(f"Tempo: {tempo}")
                    if meta_bits:
                        body.append(" | ".join(meta_bits))

                    if gate_txt and _is_gate_alert(gate_txt):
                        pdf.ln(6)
                        _ensure_space(40.0)
                        x = pdf.l_margin
                        w = page_width
                        y = float(pdf.get_y())
                        h = 14
                        if y + h > (float(pdf.h) - float(pdf.b_margin)):
                            pdf.add_page()
                            y = float(pdf.get_y())
                        pdf.set_draw_color(239, 83, 80)
                        pdf.set_line_width(1.2)
                        if hasattr(pdf, "rounded_rect"):
                            pdf.rounded_rect(x, y, w, h, 2.5)
                        else:
                            pdf.rect(x, y, w, h)
                        pdf.set_xy(x + 3, y + 2)
                        pdf.set_text_color(239, 83, 80)
                        set_font(9, bold=True)
                        pdf.cell(w - 6, 5, _safe_fpdf_text("ALERTA!"), new_x=XPos.LEFT, new_y=YPos.NEXT)
                        set_font(9, bold=False)
                        pdf.set_text_color(0, 0, 0)
                        pdf.multi_cell(w - 6, 5, _safe_fpdf_text(gate_txt), new_x=XPos.LEFT, new_y=YPos.NEXT)
                        pdf.set_y(y + h + 6)

                    for ln in (st.get("pop") or [])[:6]:
                        body.append(f"POP: {ln}")
                    for p in (st.get("pccs") or [])[:6]:
                        if isinstance(p, dict):
                            pid = p.get("id") or ""
                            par = p.get("parametro") or ""
                            lim = p.get("limite") or ""
                            acao = p.get("acao") or ""
                            body.append(f"PCC {pid}: {par}: {lim} -> {acao}" if pid else f"PCC: {par}: {lim} -> {acao}")

                    _draw_stage_box(f"{i}. {nome}", body, tier=int(rel.tier or 1))
            else:
                draw_line("PROCEDIMENTO OPERACIONAL (POP)")
                set_font(9, bold=False)
                for e in pop_etapas:
                    if isinstance(e, dict):
                        etapa = e.get("etapa") or ""
                        proc = e.get("procedimento") or ""
                        notas = e.get("notas") or ""
                        tail = f" ({notas})" if str(notas).strip() else ""
                        draw_line(f"- {etapa}: {proc}{tail}")
                    else:
                        draw_line(f"- {e}")

            pdf.ln(8)
            set_font(10, bold=True)
            pdf.ln(8)
            draw_line("PONTOS CRÍTICOS DE CONTROLE (PCC)")
            set_font(9, bold=False)
            for p in (rel.pcc_pontos or [])[:40]:
                if isinstance(p, dict):
                    parametro = p.get("parametro") or ""
                    limite = p.get("limite") or ""
                    acao = p.get("acao") or ""
                    draw_line(f"- {parametro}: {limite} -> {acao}")
                else:
                    draw_line(f"- {p}")
            _draw_footer_last_page()
            try:
                pdf.output(str(out_path))
                print(f"PDF salvo com sucesso via fpdf2: {out_path}", flush=True)
            except Exception as e:
                print(f"Erro ao salvar PDF com fpdf2: {e}", flush=True)
                raise
            return

        try:
            import html as _html
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_RIGHT
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, CondPageBreak
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus.flowables import Flowable

            def _txt(v: Any) -> str:
                s = str(v or "")
                s = s.replace("\t", " ")
                s = s.replace("•", "-")
                s = s.replace("→", "->")
                s = s.replace("↔", "<->")
                s = s.replace("⚠️", "")
                s = s.replace("⚠", "")
                s = s.replace("\r\n", "\n").replace("\r", "\n")
                return s

            def _p(v: Any) -> str:
                return _html.escape(_txt(v)).replace("\n", "<br/>")

            styles = getSampleStyleSheet()
            base = ParagraphStyle("orion_base", parent=styles["Normal"], fontName="Helvetica", fontSize=10, leading=12, wordWrap="CJK")
            h1 = ParagraphStyle("orion_h1", parent=base, fontSize=14, leading=16, spaceAfter=6)
            h2 = ParagraphStyle("orion_h2", parent=base, fontSize=12, leading=14, spaceBefore=10, spaceAfter=4)
            right = ParagraphStyle("orion_right", parent=base, alignment=TA_RIGHT)
            h_stage = ParagraphStyle("orion_stage_h", parent=base, fontName="Helvetica-Bold", fontSize=11, leading=13, textColor=colors.white)
            base_sm = ParagraphStyle("orion_sm", parent=base, fontSize=9, leading=11)
            base_mono = ParagraphStyle("orion_mono", parent=base, fontName="Helvetica", fontSize=9, leading=11)

            doc = SimpleDocTemplate(
                str(out_path),
                pagesize=A4,
                leftMargin=15 * mm,
                rightMargin=15 * mm,
                topMargin=15 * mm,
                bottomMargin=15 * mm,
                title="OrionAgroquim - Relatório",
            )

            snap = stability_snapshot or {}
            ssum = (snap.get("summary") or {}) if isinstance(snap, dict) else {}
            lab = (snap.get("lab") or {}) if isinstance(snap, dict) else {}

            def _draw_sidebar(c, _doc):
                c.saveState()
                bar_color = colors.HexColor("#1E88E5") if int(rel.tier or 1) <= 1 else colors.HexColor("#7B1FA2")
                c.setFillColor(bar_color)
                c.rect(0, 0, 5 * mm, A4[1], stroke=0, fill=1)
                c.restoreState()

            tier_border = colors.HexColor("#1E88E5") if int(rel.tier or 1) <= 1 else colors.HexColor("#7B1FA2")
            tier_header = tier_border
            tier_bg = colors.HexColor("#F5F9FF") if int(rel.tier or 1) <= 1 else colors.HexColor("#FAF5FF")

            def _is_gate_alert(text: str) -> bool:
                t = str(text or "").casefold()
                return ("não iniciar" in t) or ("alerta" in t) or ("ph >" in t)

            class AlertBox(Flowable):
                def __init__(self, text: str):
                    super().__init__()
                    self.text = str(text or "").strip()
                    self.pad = 6
                    self.gap = 4
                    self.icon_size = 10
                    self.p = Paragraph(_p(self.text), base_sm)

                def wrap(self, availWidth, availHeight):
                    self.width = availWidth
                    w = max(10, availWidth - (self.pad * 2) - self.icon_size - self.gap)
                    _, ph = self.p.wrap(w, availHeight)
                    self.height = max(ph + self.pad * 2, self.icon_size + self.pad * 2)
                    return self.width, self.height

                def draw(self):
                    c = self.canv
                    c.saveState()
                    c.setStrokeColor(colors.HexColor("#EF5350"))
                    c.setFillColor(colors.HexColor("#FFEBEE"))
                    c.setLineWidth(2)
                    c.roundRect(0, 0, self.width, self.height, 6, stroke=1, fill=1)
                    x0 = self.pad
                    y0 = (self.height - self.icon_size) / 2.0
                    c.setFillColor(colors.HexColor("#EF5350"))
                    c.setStrokeColor(colors.HexColor("#EF5350"))
                    c.setLineWidth(1)
                    c.circle(x0 + self.icon_size / 2.0, y0 + self.icon_size / 2.0, self.icon_size / 2.0, stroke=1, fill=1)
                    c.setFillColor(colors.white)
                    c.setFont("Helvetica-Bold", 9)
                    c.drawCentredString(x0 + self.icon_size / 2.0, y0 + 2, "!")
                    tw = max(10, self.width - (self.pad * 2) - self.icon_size - self.gap)
                    self.p.wrap(tw, self.height)
                    self.p.drawOn(c, self.pad + self.icon_size + self.gap, self.pad)
                    c.restoreState()

            class StageBox(Flowable):
                def __init__(self, title: str, items: List[Flowable]):
                    super().__init__()
                    self.title = str(title or "").strip()
                    self.items = list(items)
                    self.pad = 8
                    self.header_h = 18
                    self.gap = 4
                    self._wrapped: List[Tuple[Flowable, float]] = []

                def wrap(self, availWidth, availHeight):
                    self.width = availWidth
                    inner_w = max(10, availWidth - (self.pad * 2))
                    self._wrapped = []
                    total_h = self.pad + self.header_h + self.pad
                    for it in self.items:
                        iw, ih = it.wrap(inner_w, availHeight)
                        self._wrapped.append((it, ih))
                        total_h += ih + self.gap
                    if self._wrapped:
                        total_h -= self.gap
                    self.height = total_h
                    return self.width, self.height

                def draw(self):
                    c = self.canv
                    c.saveState()
                    c.setStrokeColor(tier_border)
                    c.setFillColor(tier_bg)
                    c.setLineWidth(1)
                    c.roundRect(0, 0, self.width, self.height, 8, stroke=1, fill=1)
                    c.setFillColor(tier_header)
                    c.roundRect(0, self.height - self.header_h, self.width, self.header_h, 8, stroke=0, fill=1)
                    ph = Paragraph(_p(self.title), h_stage)
                    ph.wrap(self.width - (self.pad * 2), self.header_h)
                    ph.drawOn(c, self.pad, self.height - self.header_h + 3)
                    x = self.pad
                    y = self.height - self.header_h - self.pad
                    inner_w = max(10, self.width - (self.pad * 2))
                    for it, ih in self._wrapped:
                        y -= ih
                        it.drawOn(c, x, y)
                        y -= self.gap
                    c.restoreState()

            class FooterPush(Flowable):
                def __init__(self, footer_height: float):
                    super().__init__()
                    self.footer_height = float(footer_height)
                    self._h = 0.0

                def wrap(self, availWidth, availHeight):
                    self.width = availWidth
                    self._h = max(0.0, float(availHeight) - float(self.footer_height))
                    self.height = self._h
                    return self.width, self.height

                def draw(self):
                    return

            story: List[Any] = []
            header_tbl = Table(
                [
                    [
                        Paragraph(_p("ORION AGROQUIM"), h1),
                        Paragraph(_p(f"DATA: {rel.data_hora}<br/>TIER: {rel.tier}"), right),
                    ]
                ],
                colWidths=[doc.width * 0.62, doc.width * 0.38],
            )
            header_tbl.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.append(header_tbl)
            story.append(Spacer(1, 6))
            story.append(Paragraph(_p(str(rel.titulo)), h2))
            story.append(Paragraph(_p(f"Volume Final: {get_volume()} L"), base))
            story.append(Paragraph(_p(f"Temperatura: {format_num(get_temp_c(), 1)}°C | Reator: {reactor_dd.value}"), base))
            story.append(Paragraph(_p(f"Densidade: {format_num(rel.densidade, 3)} kg/L"), base))
            story.append(Paragraph(_p(f"Balanço Hídrico: {format_num(rel.agua_balanco, 2)} kg"), base))
            if pred_line:
                story.append(Paragraph(_p(pred_line), base_sm))

            risk_level = str(ssum.get("risk_level") or "").strip().lower()
            if risk_level == "vermelho":
                risk_color = colors.HexColor("#EF5350")
                risk_text = "ALTO"
            elif risk_level == "amarelo":
                risk_color = colors.HexColor("#FFCA28")
                risk_text = "ATENÇÃO"
            elif risk_level == "verde":
                risk_color = colors.HexColor("#66BB6A")
                risk_text = "OK"
            else:
                risk_color = colors.HexColor("#BDBDBD")
                risk_text = "N/D"

            story.append(Spacer(1, 8))
            sat_val = ssum.get("best_indice_saturacao")
            sal_val = ssum.get("best_carga_sais_pct_mv")
            rr = ssum.get("risk_reasons") or []
            r0 = str(rr[0]) if rr else "-"
            stable_rows = [
                [Paragraph(_p("ESTABILIDADE (RESUMO)"), base), Paragraph(_p(f"RISCO: {risk_text}"), ParagraphStyle("rk", parent=base, fontName="Helvetica-Bold", textColor=colors.white))],
                [Paragraph(_p(f"Sat: {format_num(float(sat_val), 3) if sat_val is not None else 0.0} | Sal: {format_num(float(sal_val), 1) if sal_val is not None else 0.0}% (m/v)"), base_sm), Paragraph(_p(f"Motivo: {r0}"), base_sm)],
            ]
            stable_tbl = Table(stable_rows, colWidths=[doc.width * 0.62, doc.width * 0.38])
            stable_tbl.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CCCCCC")),
                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#F5F5F5")),
                ("BACKGROUND", (1, 0), (1, 0), risk_color),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(stable_tbl)

            targets = parse_targets_from_fields(targets_fields)
            story.append(Spacer(1, 10))
            story.append(Paragraph(_p("ALVOS (TÍTULO)"), h2))
            tgt_rows: List[List[Any]] = [[Paragraph(_p("Nutriente"), base), Paragraph(_p("%"), right)]]
            for k, label in NUTRIENT_COLUMNS:
                tv = float(targets.get(k, 0.0) or 0.0)
                if tv > 0:
                    tgt_rows.append([Paragraph(_p(label), base), Paragraph(_p(f"{tv:.3f}"), right)])
            if len(tgt_rows) == 1:
                tgt_rows.append([Paragraph(_p("-"), base), Paragraph(_p("-"), right)])
            tgt_tbl = Table(tgt_rows, colWidths=[doc.width * 0.72, doc.width * 0.28])
            tgt_tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 10),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CCCCCC")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(tgt_tbl)

            story.append(Spacer(1, 10))
            story.append(Paragraph(_p("COMPOSIÇÃO DE CARGA (BOM)"), h2))
            bom_rows: List[List[Any]] = [[Paragraph(_p("Insumo"), base), Paragraph(_p("Massa (kg)"), right)]]
            for l in (rel.bom_lines or []):
                bom_rows.append([Paragraph(_p(_txt(l.insumo_nome)), base), Paragraph(_p(f"{float(l.massa_kg):.3f}"), right)])
            tbl = Table(bom_rows, colWidths=[doc.width * 0.75, doc.width * 0.25])
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 10),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CCCCCC")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(tbl)

            story.append(Spacer(1, 10))
            story.append(Paragraph(_p("ESTABILIDADE (DETALHES)"), h2))
            if ssum:
                alerts = ssum.get("best_alerts") or []
                if alerts:
                    for a in alerts[:20]:
                        story.append(Paragraph(_p(f"- {a}"), base_sm))
                rr2 = ssum.get("risk_reasons") or []
                if rr2:
                    story.append(Spacer(1, 4))
                    for r in rr2[:20]:
                        story.append(Paragraph(_p(f"- {r}"), base_sm))
            else:
                story.append(Paragraph(_p("Sem diagnóstico disponível (nenhum cálculo enviado à aba Estabilidade)."), base_sm))
            if lab:
                story.append(Spacer(1, 10))
                story.append(Paragraph(_p("BANCADA"), h2))
                story.append(Paragraph(_p(f"pH: {lab.get('ph')}"), base))
                story.append(Paragraph(_p(f"Condutividade (mS/cm): {lab.get('ec')}"), base))
                story.append(Paragraph(_p(f"Turbidez (NTU): {lab.get('turbidez')}"), base))
                obs = str(lab.get("observacoes") or "").strip()
                if obs:
                    story.append(Paragraph(_p(f"Observações: {obs}"), base))

            story.append(Spacer(1, 10))
            pop_etapas = list(rel.pop_etapas or [])
            if pop_etapas and isinstance(pop_etapas[0], dict) and ("nome_etapa" in pop_etapas[0]):
                story.append(Paragraph(_p("ROTEIRO DE PRODUÇÃO INDUSTRIAL"), h2))
                for i, st in enumerate(pop_etapas, start=1):
                    nome = st.get("nome_etapa") or f"Etapa {i}"
                    instr = st.get("instrucao_processo") or ""
                    tempo = st.get("tempo") or ""
                    pm = st.get("parametros_maquina") or {}
                    rpm = pm.get("rpm")
                    tc = pm.get("temp_c")
                    gate = st.get("gate_ph") or {}
                    gate_txt = str(gate.get("texto") or "").strip()
                    meta_bits = []
                    if rpm is not None and str(rpm).strip():
                        meta_bits.append(f"RPM: {rpm}")
                    if tc is not None and str(tc).strip():
                        meta_bits.append(f"Temperatura: {tc}")
                    if str(tempo).strip():
                        meta_bits.append(f"Tempo: {tempo}")

                    items: List[Flowable] = []
                    if str(instr).strip():
                        if i == 3 or "dissol" in str(nome).casefold():
                            dlines = _dissolution_lines(str(instr))
                            for j, ln in enumerate(dlines):
                                items.append(Paragraph(_p(ln), base if j == 0 else base_sm))
                        else:
                            items.append(Paragraph(_p(str(instr)), base))
                    if meta_bits:
                        items.append(Paragraph(_p(" | ".join(meta_bits)), base_sm))
                    if gate_txt and _is_gate_alert(gate_txt):
                        items.append(AlertBox(gate_txt))
                    elif gate_txt:
                        items.append(Paragraph(_p(gate_txt), base_sm))
                    for ln in (st.get("pop") or [])[:6]:
                        items.append(Paragraph(_p(f"POP: {ln}"), base_sm))
                    for p in (st.get("pccs") or [])[:6]:
                        if isinstance(p, dict):
                            pid = p.get("id") or ""
                            par = p.get("parametro") or ""
                            lim = p.get("limite") or ""
                            acao = p.get("acao") or ""
                            txt = f"PCC {pid}: {par}: {lim} -> {acao}" if pid else f"PCC: {par}: {lim} -> {acao}"
                            items.append(Paragraph(_p(txt), base_sm))
                    story.append(CondPageBreak(40 * mm))
                    story.append(StageBox(f"{i}. {nome}", items))
                    story.append(Spacer(1, 6))
            else:
                story.append(Paragraph(_p("PROCEDIMENTO OPERACIONAL (POP)"), h2))
                for e in pop_etapas:
                    if isinstance(e, dict):
                        story.append(Paragraph(_p(f"- {e.get('etapa','')}: {e.get('procedimento','')} ({e.get('notas','')})"), base))
                    else:
                        story.append(Paragraph(_p(f"- {e}"), base))

            story.append(Spacer(1, 10))
            story.append(Paragraph(_p("PONTOS CRÍTICOS DE CONTROLE (PCC)"), h2))
            for p in (rel.pcc_pontos or []):
                story.append(Paragraph(_p(f"! {p.get('parametro','')}: {p.get('limite','')} -> {p.get('acao','')}"), base))

            footer_height = 38 * mm
            story.append(FooterPush(footer_height))
            story.append(Paragraph(_p("CHECKLIST DE LIBERAÇÃO (A4)"), h2))
            story.append(Paragraph(_p("\n".join([
                "[ ] Aparência homogênea (sem grumos/cristais visíveis)",
                "[ ] pH final registrado (alvo conforme TDS)",
                "[ ] Densidade registrada",
                "[ ] Filtrabilidade / bico ok (se aplicável)",
                "[ ] Amostra retida e identificada",
            ])), base_sm))
            story.append(Spacer(1, 6))
            story.append(Paragraph(_p("REGISTRO DO LOTE"), h2))
            story.append(Paragraph(_p("Lote: ____________________   Data: ____/____/______   Responsável: ____________________\nAssinatura: _________________________________________________"), base_sm))

            doc.build(story, onFirstPage=_draw_sidebar, onLaterPages=_draw_sidebar)
        except Exception as e:
            print(f"Erro ao renderizar PDF com reportlab: {e}", flush=True)
            raise

<<<<<<< HEAD
    def on_generate_pdf(_e):
=======
    def on_generate_pdf(_e=None):
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
        nonlocal current_relatorio
        if not current_relatorio:
            page.snack_bar = ft.SnackBar(ft.Text("Nenhum laudo carregado. Use ENVIAR PARA LAUDO / OP em uma fórmula."))
            page.snack_bar.open = True
            page.update()
            return

        try:
            exports_dir = _exports_dir()
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = exports_dir / f"Relatorio_{stamp}.pdf"
            if out_path.exists():
                bump = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                out_path = exports_dir / f"Relatorio_{bump}.pdf"

            print(f"Iniciando geração de PDF em: {out_path}", flush=True)
            snap = stability_module.last_snapshot()
            print("Snapshot de estabilidade obtido", flush=True)
            _render_pdf(current_relatorio, out_path, snap)
            print(f"PDF renderizado com sucesso em: {out_path}", flush=True)
            if (not out_path.exists()) or (out_path.stat().st_size <= 0):
                raise RuntimeError("Arquivo PDF não foi criado (tamanho zero).")

            try:
                os.startfile(str(out_path))
            except Exception as ex:
                msg = f"Erro ao abrir PDF: {ex}"
                print(msg, flush=True)

            page.snack_bar = ft.SnackBar(ft.Text(f"PDF gerado: {out_path}"))
            page.snack_bar.open = True
            page.update()
        except Exception as ex:
            import traceback
            error_msg = f"Falha ao gerar PDF: {str(ex)}"
            print(f"{error_msg}\n{traceback.format_exc()}", flush=True)
            page.snack_bar = ft.SnackBar(ft.Text(error_msg))
            page.snack_bar.open = True
            page.update()

<<<<<<< HEAD
    def on_save_history(_e):
=======
    def on_save_history(_e=None):
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
        nonlocal current_relatorio
        if not current_relatorio:
            page.snack_bar = ft.SnackBar(ft.Text("Nenhum laudo carregado para salvar no histórico."))
            page.snack_bar.open = True
            page.update()
            return

        try:
            exports_dir = _exports_dir()
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pdf_path = exports_dir / f"Relatorio_{stamp}.pdf"
            if pdf_path.exists():
                bump = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                pdf_path = exports_dir / f"Relatorio_{bump}.pdf"

            print(f"Iniciando salvamento de PDF em: {pdf_path}", flush=True)
            snap = stability_module.last_snapshot()
            print("Snapshot de estabilidade obtido", flush=True)
            _render_pdf(current_relatorio, pdf_path, snap)
            print(f"PDF renderizado com sucesso em: {pdf_path}", flush=True)
            if (not pdf_path.exists()) or (pdf_path.stat().st_size <= 0):
                raise RuntimeError("Arquivo PDF não foi criado (tamanho zero).")
            
            try:
                os.startfile(str(pdf_path))
            except Exception as e:
                msg = f"Erro ao abrir PDF: {e}"
                print(msg, flush=True)

            entry = _serialize_relatorio(current_relatorio)
            entry["pdf_path"] = str(pdf_path)
            report_history.append(entry)
            page.snack_bar = ft.SnackBar(ft.Text(f"PDF salvo: {pdf_path}"))
            page.snack_bar.open = True
        except Exception as ex:
            import traceback
            error_msg = f"Falha ao salvar: {str(ex)}"
            print(f"{error_msg}\n{traceback.format_exc()}", flush=True)
            page.snack_bar = ft.SnackBar(ft.Text(error_msg))
            page.snack_bar.open = True
        _refresh_history_list()



    reports_view = ft.Row(
        [
            ft.Container(
                width=420,
                padding=15,
                border=ft.Border.all(1, ft.Colors.GREY_800),
                border_radius=10,
                content=ft.Column(
                    [
                        ft.Text("Relatório e POP", size=18, weight=ft.FontWeight.BOLD),
                        ft.Row(
                            [
<<<<<<< HEAD
                                ft.ElevatedButton("GERAR PDF", icon=ft.Icons.PICTURE_AS_PDF, on_click=on_generate_pdf),
                                ft.ElevatedButton("SALVAR NO HISTÓRICO", icon=ft.Icons.SAVE, on_click=on_save_history),
=======
                                        ft.Button(content="GERAR PDF", icon=ft.Icons.PICTURE_AS_PDF, on_click=on_generate_pdf),
                                        ft.Button(content="SALVAR NO HISTÓRICO", icon=ft.Icons.SAVE, on_click=on_save_history),
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
                            ],
                            wrap=True,
                        ),
                        ft.Divider(),
                        ft.Text("Histórico", size=14, weight=ft.FontWeight.BOLD),
                        report_history_list,
                    ],
                    spacing=10,
                    expand=True,
                ),
            ),
            ft.Container(
                expand=True,
                padding=0,
                content=ft.Container(padding=20, content=laudo_content, expand=True),
            ),
        ],
        expand=True,
        spacing=20,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    main_tabs = make_tabs(
        ["⚗️ FORMULAÇÃO", "⚖️ ESTABILIDADE", "📋 RELATÓRIO & POP"],
        [
            ft.Container(padding=0, content=calc_tabs, expand=True),
            ft.Container(padding=20, content=stability_module.view, expand=True),
            ft.Container(padding=20, content=reports_view, expand=True),
        ],
        selected_index=0,
        expand=True,
    )

    def on_reset_all(_e) -> None:
        nonlocal limite_diversificacao, max_saturation_index, current_relatorio, report_history

        volume_field.value = str(int(DEFAULT_VOLUME_L))
        temp_field.value = "25"
        reactor_dd.value = "3"
        supply_chain_switch.value = False

        numpy_switch.value = True
        scipy_switch.value = False
        anti_crystal_switch.value = False
        max_saturation_index = 1.0
        max_saturation_text.value = "Índice de saturação máx: 1.00"

        limite_diversificacao = 75.0
        limite_diversificacao_slider.value = 75.0
        limite_diversificacao_text.value = "Limite de Concentração por Fonte (%): 75"

        for tf in targets_fields.values():
            tf.value = ""

        principal_thermo_alert.content = ft.Container()
        principal_viability_container.content = ft.Container()
        principal_table_container.content = ft.Container()
        principal_reco_container.content = ft.Container()
        principal_title_text.value = "Formulação 1"
        principal_subtitle_text.value = "Aguardando cálculo."

        set_tabs(top12_tabs, ["Opção 1"], [ft.Container()], selected_index=0)

        manual_lines.clear()
        for k in list(manual_selected_nutrients.keys()):
            manual_selected_nutrients[k] = False
        manual_active_nutrient_dd.value = None
        manual_insumo_dd.value = None
        manual_target_tf.value = ""
        update_manual_ui()
        manual_table_container.content = ft.Container()
        manual_thermo_alert.content = ft.Container()
        manual_reco_container.content = ft.Container()

        stability_module.reset()

        current_relatorio = None
        laudo_content.controls.clear()
        report_history.clear()
        _refresh_history_list()

        main_tabs.selected_index = 0
        calc_tabs.selected_index = 0
        reload_data()
        page.update()

    # --- AUXILIARES DE RENDERIZAÇÃO ---

<<<<<<< HEAD
=======
    def _render_estudo_chart(dados: Dict[str, Any]) -> ft.Control:
        if not isinstance(dados, dict):
            return ft.Container()
        tp = str(dados.get("tipo") or "").strip().casefold()
        titulo = str(dados.get("titulo") or "").strip()
        header = ft.Text(titulo, size=12, weight=ft.FontWeight.BOLD) if titulo else ft.Container()

        if tp == "indicador":
            v = float(dados.get("valor") or 0.0)
            unidade = str(dados.get("unidade") or "").strip()
            pb = ft.ProgressBar(value=min(1.0, max(0.0, v / 100.0)))
            return ft.Container(
                content=ft.Column(
                    [
                        header,
                        ft.Row([ft.Text(f"{format_num(v, 1)} {unidade}".strip(), weight=ft.FontWeight.BOLD), pb], spacing=10),
                    ],
                    spacing=6,
                ),
                padding=10,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.WHITE)),
                border_radius=10,
            )

        if tp == "barras":
            rows = []
            for d in list(dados.get("dados") or [])[:10]:
                ins = str(d.get("insumo") or "")
                pct = float(d.get("contrib_pct_saturacao") or 0.0)
                rows.append(
                    ft.DataRow(
                        [
                            ft.DataCell(ft.Text(ins, size=11)),
                            ft.DataCell(ft.Text(f"{pct:.1f}%", size=11)),
                        ]
                    )
                )
            table = ft.DataTable(
                columns=[ft.DataColumn(ft.Text("Insumo")), ft.DataColumn(ft.Text("% Saturação"))],
                rows=rows or [ft.DataRow(cells=[ft.DataCell(ft.Text("-")), ft.DataCell(ft.Text("-"))])],
            )
            return ft.Container(content=ft.Column([header, table], spacing=8), padding=10, border_radius=10)

        if tp == "barras_duplas":
            rows = []
            for d in list(dados.get("dados") or [])[:10]:
                ins = str(d.get("insumo") or "")
                q = float(d.get("calor_kj") or 0.0)
                kind = str(d.get("tipo") or "")
                rows.append(ft.DataRow(cells=[ft.DataCell(ft.Text(ins, size=11)), ft.DataCell(ft.Text(f"{q:+.1f} kJ", size=11)), ft.DataCell(ft.Text(kind, size=11))]))
            table = ft.DataTable(
                columns=[ft.DataColumn(ft.Text("Insumo")), ft.DataColumn(ft.Text("Calor")), ft.DataColumn(ft.Text("Tipo"))],
                rows=rows or [ft.DataRow(cells=[ft.DataCell(ft.Text("-")), ft.DataCell(ft.Text("-")), ft.DataCell(ft.Text("-"))])],
            )
            resumo = dados.get("resumo") or {}
            meta = ""
            try:
                if isinstance(resumo, dict):
                    tin = resumo.get("temp_entrada_c")
                    tout = resumo.get("temp_saida_c")
                    dt = resumo.get("delta_t_c")
                    meta = f"T: {format_num(float(tin), 0)}°C → {format_num(float(tout), 1)}°C | ΔT: {format_num(float(dt), 1)}°C"
            except Exception:
                meta = ""
            meta_ctrl = ft.Text(meta, size=11, italic=True) if meta else ft.Container()
            return ft.Container(content=ft.Column([header, meta_ctrl, table], spacing=8), padding=10, border_radius=10)

        if tp == "radar":
            rows = []
            for d in list(dados.get("dados") or [])[:25]:
                nutr = str(d.get("sigla") or "")
                alvo = float(d.get("alvo_pct") or 0.0)
                obt = float(d.get("obtido_pct") or 0.0)
                ating = float(d.get("atingido_pct") or 0.0)
                pb = ft.ProgressBar(value=min(1.0, max(0.0, (ating / 100.0) if math.isfinite(ating) else 0.0)))
                rows.append(
                    ft.DataRow(
                        [
                            ft.DataCell(ft.Text(nutr, size=11)),
                            ft.DataCell(ft.Text(f"{alvo:.3f}", size=11)),
                            ft.DataCell(ft.Text(f"{obt:.3f}", size=11)),
                            ft.DataCell(ft.Text(f"{ating:.1f}%", size=11)),
                            ft.DataCell(pb),
                        ]
                    )
                )
            table = ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("Nutr.")),
                    ft.DataColumn(ft.Text("Alvo %")),
                    ft.DataColumn(ft.Text("Obt. %")),
                    ft.DataColumn(ft.Text("Ating. %")),
                    ft.DataColumn(ft.Text("Barra")),
                ],
                rows=rows
                or [
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text("-")),
                            ft.DataCell(ft.Text("-")),
                            ft.DataCell(ft.Text("-")),
                            ft.DataCell(ft.Text("-")),
                            ft.DataCell(ft.Text("-")),
                        ]
                    )
                ],
            )
            return ft.Container(content=ft.Column([header, table], spacing=8), padding=10, border_radius=10)

        return ft.Container()

    def _serialize_estudo_text(idx: int, secoes: Sequence[estudo_quimico.SecaoEstudo]) -> str:
        out: List[str] = []
        out.append(f"ESTUDO QUÍMICO - F{idx}")
        out.append(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        out.append("")
        for s in list(secoes or []):
            out.append("=" * 80)
            out.append(str(s.titulo or ""))
            out.append("=" * 80)
            if getattr(s, "alerta", None):
                out.append(f"ALERTA: {s.alerta}")
            if getattr(s, "recomendacao", None):
                out.append(f"RECOMENDAÇÃO: {s.recomendacao}")
            if getattr(s, "quimica", ""):
                out.append("")
                out.append("QUÍMICA:")
                out.append(str(s.quimica))
            if getattr(s, "matematica", ""):
                out.append("")
                out.append("MATEMÁTICA:")
                out.append(str(s.matematica))
            if getattr(s, "logica", ""):
                out.append("")
                out.append("LÓGICA:")
                out.append(str(s.logica))
            if getattr(s, "python", ""):
                out.append("")
                out.append("PYTHON:")
                out.append(str(s.python))
            if getattr(s, "dados", None):
                try:
                    out.append("")
                    out.append("DADOS (resumo):")
                    out.append(str(s.dados))
                except Exception:
                    pass
            out.append("")
        return "\n".join(out).strip() + "\n"

    def _notify(msg: str) -> None:
        try:
            sb = ft.SnackBar(ft.Text(msg))
            try:
                page.overlay.append(sb)
            except Exception:
                pass
            sb.open = True
            page.update()
        except Exception:
            pass

    def _save_estudo_report(idx: int, secoes: Sequence[estudo_quimico.SecaoEstudo]) -> None:
        try:
            exports_dir = _exports_dir()
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = exports_dir / f"Estudo_F{idx}_{stamp}.txt"
            if out_path.exists():
                bump = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                out_path = exports_dir / f"Estudo_F{idx}_{bump}.txt"
            out_path.write_text(_serialize_estudo_text(idx, secoes), encoding="utf-8", errors="replace")
            try:
                os.startfile(str(out_path))
            except Exception:
                pass
            _notify(f"Estudo salvo: {out_path}")
        except Exception as ex:
            _notify(f"Falha ao salvar estudo: {ex}")

    def _save_estudo_report_pdf(idx: int, secoes: Sequence[estudo_quimico.SecaoEstudo]) -> None:
        try:
            exports_dir = _exports_dir()
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = exports_dir / f"Estudo_F{idx}_{stamp}.pdf"
            if out_path.exists():
                bump = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                out_path = exports_dir / f"Estudo_F{idx}_{bump}.pdf"

            try:
                import reportlab
                using_reportlab = True
            except ModuleNotFoundError:
                using_reportlab = False

            def _sanitize_text(v: Any) -> str:
                s = str(v or "")
                s = s.replace("\t", " ")
                s = s.replace("•", "-")
                s = s.replace("→", "->")
                s = s.replace("↔", "<->")
                s = s.replace("\r\n", "\n").replace("\r", "\n")
                return s

            def _extract_rows_from_dados(d: Any) -> Optional[Dict[str, Any]]:
                if not isinstance(d, dict):
                    return None
                tipo = str(d.get("tipo") or "").strip()
                titulo = str(d.get("titulo") or "").strip()
                items = d.get("dados")
                if not isinstance(items, list) or not items:
                    return None

                if tipo == "barras":
                    headers = ["Insumo", "Massa (kg)", "Limite (kg)", "Saturação (%)"]
                    rows = []
                    for it in items:
                        if not isinstance(it, dict):
                            continue
                        rows.append([
                            str(it.get("insumo", "") or ""),
                            format_num(float(it.get("massa_kg", 0.0) or 0.0), 3),
                            format_num(float(it.get("limite_kg", 0.0) or 0.0), 3),
                            format_num(float(it.get("contrib_pct_saturacao", 0.0) or 0.0), 1),
                        ])
                    return {"titulo": titulo or "Tabela", "headers": headers, "rows": rows}

                if tipo == "barras_duplas":
                    headers = ["Insumo", "Massa (kg)", "ΔH (kJ/kg)", "Calor (kJ)", "Tipo"]
                    rows = []
                    for it in items:
                        if not isinstance(it, dict):
                            continue
                        rows.append([
                            str(it.get("insumo", "") or ""),
                            format_num(float(it.get("massa_kg", 0.0) or 0.0), 3),
                            format_num(float(it.get("delta_h_kj_kg", 0.0) or 0.0), 0),
                            format_num(float(it.get("calor_kj", 0.0) or 0.0), 1),
                            str(it.get("tipo", "") or ""),
                        ])
                    return {"titulo": titulo or "Tabela", "headers": headers, "rows": rows}

                if tipo == "radar":
                    headers = ["Nutriente", "Alvo (%)", "Obtido (%)", "Diferença", "Atingido (%)"]
                    rows = []
                    for it in items:
                        if not isinstance(it, dict):
                            continue
                        rows.append([
                            str(it.get("nutriente", "") or ""),
                            format_num(float(it.get("alvo_pct", 0.0) or 0.0), 3),
                            format_num(float(it.get("obtido_pct", 0.0) or 0.0), 3),
                            format_num(float(it.get("diferenca", 0.0) or 0.0), 3),
                            format_num(float(it.get("atingido_pct", 0.0) or 0.0), 1),
                        ])
                    return {"titulo": titulo or "Tabela", "headers": headers, "rows": rows}

                return None

            if using_reportlab:
                from xml.sax.saxutils import escape

                from reportlab.lib import colors
                from reportlab.lib.pagesizes import A4
                from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
                from reportlab.pdfbase import pdfmetrics
                from reportlab.pdfbase.ttfonts import TTFont
                from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

                def _find_font(candidates: List[str]) -> Optional[str]:
                    for p in candidates:
                        try:
                            if Path(p).exists():
                                return p
                        except Exception:
                            pass
                    return None

                normal_candidates = [
                    r"C:\Windows\Fonts\segoeui.ttf",
                    r"C:\Windows\Fonts\arial.ttf",
                    r"C:\Windows\Fonts\calibri.ttf",
                ]
                mono_candidates = [
                    r"C:\Windows\Fonts\consola.ttf",
                    r"C:\Windows\Fonts\cascadiamono.ttf",
                    r"C:\Windows\Fonts\cour.ttf",
                ]

                normal_font = _find_font(normal_candidates)
                mono_font = _find_font(mono_candidates)

                font_name = "Helvetica"
                font_bold = "Helvetica-Bold"
                font_italic = "Helvetica-Oblique"
                mono_name = "Courier"

                try:
                    if normal_font:
                        pdfmetrics.registerFont(TTFont("OrionRL", normal_font))
                        font_name = "OrionRL"
                        font_bold = "OrionRL"
                        font_italic = "OrionRL"
                except Exception:
                    pass

                try:
                    if mono_font:
                        pdfmetrics.registerFont(TTFont("OrionMonoRL", mono_font))
                        mono_name = "OrionMonoRL"
                except Exception:
                    pass

                doc = SimpleDocTemplate(
                    str(out_path),
                    pagesize=A4,
                    leftMargin=36,
                    rightMargin=36,
                    topMargin=36,
                    bottomMargin=36,
                    title=f"Estudo F{idx}",
                )

                styles = getSampleStyleSheet()
                style_title = ParagraphStyle("orion_title", parent=styles["Heading1"], fontName=font_bold, fontSize=16, leading=20, spaceAfter=10)
                style_h2 = ParagraphStyle("orion_h2", parent=styles["Heading2"], fontName=font_bold, fontSize=13, leading=16, spaceAfter=6)
                style_body = ParagraphStyle("orion_body", parent=styles["BodyText"], fontName=font_name, fontSize=11, leading=14, spaceAfter=6)
                style_logic = ParagraphStyle("orion_logic", parent=styles["BodyText"], fontName=font_italic, fontSize=10, leading=13, textColor=colors.HexColor("#3C3C3C"), spaceAfter=6)
                style_code = ParagraphStyle("orion_code", parent=styles["BodyText"], fontName=mono_name, fontSize=9, leading=11, textColor=colors.HexColor("#00FF00"))
                style_math = ParagraphStyle("orion_math", parent=styles["BodyText"], fontName=mono_name, fontSize=11, leading=14, textColor=colors.HexColor("#006064"))

                def _p(txt: str) -> Paragraph:
                    t = escape(_sanitize_text(txt)).replace("\n\n", "<br/><br/>").replace("\n", "<br/>")
                    return Paragraph(t, style_body)

                def _p_logic(txt: str) -> Paragraph:
                    t = escape(_sanitize_text(txt)).replace("\n\n", "<br/><br/>").replace("\n", "<br/>")
                    return Paragraph(t, style_logic)

                def _box_1cell(txt: str, *, bg: Any, style: ParagraphStyle, pad: int = 8) -> Table:
                    t = escape(_sanitize_text(txt)).replace("\n", "<br/>")
                    tbl = Table([[Paragraph(t, style)]], colWidths=["*"])
                    tbl.setStyle(
                        TableStyle(
                            [
                                ("BACKGROUND", (0, 0), (-1, -1), bg),
                                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CCCCCC")),
                                ("LEFTPADDING", (0, 0), (-1, -1), pad),
                                ("RIGHTPADDING", (0, 0), (-1, -1), pad),
                                ("TOPPADDING", (0, 0), (-1, -1), pad),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
                            ]
                        )
                    )
                    return tbl

                def _data_table(titulo: str, headers: List[str], rows: List[List[str]]) -> List[Any]:
                    data = [headers] + rows
                    tbl = Table(data, repeatRows=1)
                    tbl.setStyle(
                        TableStyle(
                            [
                                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F0F0F0")),
                                ("FONTNAME", (0, 0), (-1, 0), font_bold),
                                ("FONTSIZE", (0, 0), (-1, -1), 9),
                                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D0D0D0")),
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
                            ]
                        )
                    )
                    return [Paragraph(escape(titulo), style_h2), tbl, Spacer(1, 10)]

                story: List[Any] = []
                story.append(Paragraph(f"Relatório de Estudo — F{idx}", style_title))
                story.append(Paragraph(escape(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"), style_body))
                story.append(Spacer(1, 12))

                for s in list(secoes or []):
                    story.append(Paragraph(escape(_sanitize_text(getattr(s, "titulo", "") or "").replace("📊", "").strip()), style_h2))

                    if getattr(s, "alerta", None):
                        story.append(_box_1cell(str(s.alerta), bg=colors.HexColor("#FFEBEE"), style=ParagraphStyle("orion_alert", parent=style_body, textColor=colors.HexColor("#C62828"), fontName=font_bold)))
                        story.append(Spacer(1, 6))

                    if getattr(s, "recomendacao", None):
                        story.append(_box_1cell(str(s.recomendacao), bg=colors.HexColor("#E8F5E9"), style=ParagraphStyle("orion_reco", parent=style_body, textColor=colors.HexColor("#1B5E20"), fontName=font_bold)))
                        story.append(Spacer(1, 6))

                    quim = str(getattr(s, "quimica", "") or "")
                    if quim.strip():
                        story.append(_p(quim))

                    mat = str(getattr(s, "matematica", "") or "")
                    if mat.strip():
                        story.append(_box_1cell(mat, bg=colors.HexColor("#F0F0F0"), style=style_math))
                        story.append(Spacer(1, 6))

                    logi = str(getattr(s, "logica", "") or "")
                    if logi.strip():
                        story.append(_p_logic(logi))

                    py = str(getattr(s, "python", "") or "")
                    if py.strip():
                        story.append(_box_1cell(py, bg=colors.black, style=style_code, pad=10))
                        story.append(Spacer(1, 6))

                    tbl = _extract_rows_from_dados(getattr(s, "dados", None))
                    if tbl:
                        story.extend(_data_table(tbl["titulo"], tbl["headers"], tbl["rows"]))

                    story.append(Spacer(1, 14))
                    if len(story) > 0 and (len(story) % 60 == 0):
                        story.append(PageBreak())

                doc.build(story)
                try:
                    os.startfile(str(out_path))
                except Exception:
                    pass
                _notify(f"Estudo PDF salvo: {out_path}")
                return

            try:
                from fpdf import FPDF
                try:
                    from fpdf.enums import XPos, YPos
                except Exception:
                    class _XPos:
                        LMARGIN = "LMARGIN"

                    class _YPos:
                        NEXT = "NEXT"

                    XPos = _XPos
                    YPos = _YPos
            except ModuleNotFoundError:
                raise

            class OrionStudyPDF(FPDF):
                def header(self):
                    self.set_fill_color(30, 136, 229)
                    self.rect(0, 0, 5, float(self.h), style="F")

            pdf = OrionStudyPDF()
            pdf.set_margins(15, 15, 15)
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()

            using_unicode_font = False
            using_unicode_mono = False
            try:
                font_candidates = [
                    r"C:\Windows\Fonts\arial.ttf",
                    r"C:\Windows\Fonts\segoeui.ttf",
                    r"C:\Windows\Fonts\calibri.ttf",
                ]
                font_path = next((p for p in font_candidates if Path(p).exists()), None)
                if font_path:
                    pdf.add_font("OrionFont", "", font_path, uni=True)
                    pdf.add_font("OrionFont", "B", font_path, uni=True)
                    pdf.add_font("OrionFont", "I", font_path, uni=True)
                    using_unicode_font = True
            except Exception:
                using_unicode_font = False

            try:
                mono_candidates = [
                    r"C:\Windows\Fonts\consola.ttf",
                    r"C:\Windows\Fonts\cascadiamono.ttf",
                    r"C:\Windows\Fonts\cour.ttf",
                ]
                mono_path = next((p for p in mono_candidates if Path(p).exists()), None)
                if mono_path:
                    pdf.add_font("OrionMono", "", mono_path, uni=True)
                    pdf.add_font("OrionMono", "B", mono_path, uni=True)
                    using_unicode_mono = True
            except Exception:
                using_unicode_mono = False

            def _safe_txt(v: Any) -> str:
                s = _sanitize_text(v)
                if using_unicode_font or using_unicode_mono:
                    return s
                try:
                    return s.encode("latin-1", "replace").decode("latin-1")
                except Exception:
                    return s

            def set_font(size: int, *, bold: bool = False, italic: bool = False) -> None:
                if using_unicode_font:
                    style = ("B" if bold else "") + ("I" if italic else "")
                    pdf.set_font("OrionFont", style=style, size=size)
                else:
                    style = ("B" if bold else "") + ("I" if italic else "")
                    pdf.set_font("Helvetica", style=style, size=size)

            def set_mono(size: int, *, bold: bool = False) -> None:
                if using_unicode_mono:
                    pdf.set_font("OrionMono", style=("B" if bold else ""), size=size)
                elif using_unicode_font:
                    pdf.set_font("OrionFont", style=("B" if bold else ""), size=size)
                else:
                    pdf.set_font("Courier", style=("B" if bold else ""), size=size)

            def spacer(mm: float) -> None:
                pdf.ln(mm)

            def h1(txt: str) -> None:
                set_font(16, bold=True)
                pdf.set_text_color(0, 0, 0)
                pdf.multi_cell(0, 8, text=_safe_txt(txt), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                spacer(2)

            def h2(txt: str) -> None:
                set_font(13, bold=True)
                pdf.set_text_color(0, 0, 0)
                pdf.multi_cell(0, 7, text=_safe_txt(txt), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                spacer(1)

            def para(txt: str) -> None:
                t = _safe_txt(txt).strip()
                if not t:
                    return
                set_font(11)
                pdf.set_text_color(30, 30, 30)
                pdf.multi_cell(0, 5, text=t, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                spacer(1)

            def alert_box(txt: str, *, kind: str) -> None:
                t = _safe_txt(txt).strip()
                if not t:
                    return
                if kind == "alert":
                    pdf.set_fill_color(255, 235, 238)
                    pdf.set_text_color(198, 40, 40)
                else:
                    pdf.set_fill_color(232, 245, 233)
                    pdf.set_text_color(27, 94, 32)
                set_font(10, bold=True)
                pdf.multi_cell(0, 5, text=t, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_text_color(30, 30, 30)
                spacer(1)

            def math_box(txt: str) -> None:
                t = _safe_txt(txt).strip()
                if not t:
                    return
                pdf.set_fill_color(240, 240, 240)
                pdf.set_text_color(0, 96, 100)
                set_mono(11, bold=True)
                pdf.multi_cell(0, 6, text=t, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_text_color(30, 30, 30)
                spacer(1)

            def logic_block(txt: str) -> None:
                t = _safe_txt(txt).strip()
                if not t:
                    return
                set_font(10, italic=True)
                pdf.set_text_color(60, 60, 60)
                pdf.multi_cell(0, 5, text=t, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_text_color(30, 30, 30)
                spacer(1)

            def python_box(txt: str) -> None:
                t = _safe_txt(txt).strip()
                if not t:
                    return
                pdf.set_fill_color(0, 0, 0)
                pdf.set_text_color(0, 255, 0)
                set_mono(9)
                for ln in t.splitlines():
                    pdf.multi_cell(0, 4.5, text=ln.rstrip(), fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_text_color(30, 30, 30)
                spacer(1)

            def table_block(titulo: str, headers: List[str], rows: List[List[str]]) -> None:
                if not headers or not rows:
                    return
                h2(titulo)
                set_mono(9, bold=True)
                pdf.set_fill_color(240, 240, 240)
                pdf.set_text_color(0, 0, 0)

                def _col_widths() -> List[int]:
                    widths = [len(h) for h in headers]
                    for r in rows[:30]:
                        for i, c in enumerate(r):
                            widths[i] = max(widths[i], len(str(c)))
                    widths = [min(w, 48) for w in widths]
                    return widths

                colw = _col_widths()
                header_line = "  ".join(str(headers[i])[:colw[i]].ljust(colw[i]) for i in range(len(headers)))
                pdf.multi_cell(0, 5, text=_safe_txt(header_line), fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

                set_mono(9)
                pdf.set_text_color(20, 20, 20)
                for idx_row, r in enumerate(rows):
                    if idx_row % 2 == 0:
                        pdf.set_fill_color(255, 255, 255)
                    else:
                        pdf.set_fill_color(245, 245, 245)
                    line = "  ".join(str(r[i])[:colw[i]].ljust(colw[i]) for i in range(len(headers)))
                    pdf.multi_cell(0, 4.8, text=_safe_txt(line), fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                spacer(1)

            h1(f"Relatório de Estudo — F{idx}")
            para(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
            spacer(2)

            for s in list(secoes or []):
                h2(_sanitize_text(getattr(s, "titulo", "") or "").replace("📊", "").strip())
                if getattr(s, "alerta", None):
                    alert_box(str(s.alerta), kind="alert")
                if getattr(s, "recomendacao", None):
                    alert_box(str(s.recomendacao), kind="reco")

                quim = str(getattr(s, "quimica", "") or "")
                if quim.strip():
                    para(quim)
                mat = str(getattr(s, "matematica", "") or "")
                if mat.strip():
                    math_box(mat)
                logi = str(getattr(s, "logica", "") or "")
                if logi.strip():
                    logic_block(logi)
                py = str(getattr(s, "python", "") or "")
                if py.strip():
                    python_box(py)

                tbl = _extract_rows_from_dados(getattr(s, "dados", None))
                if tbl:
                    table_block(tbl["titulo"], tbl["headers"], tbl["rows"])

                spacer(3)

            pdf.output(str(out_path))
            try:
                os.startfile(str(out_path))
            except Exception:
                pass
            _notify(f"Estudo PDF salvo: {out_path}")
        except Exception as ex:
            _notify(f"Falha ao salvar estudo PDF: {ex}")

    def _open_estudo_dialog(idx: int, output: FormulaOutput) -> None:
        try:
            print(f"[ESTUDO] Clique em ESTUDAR: F{idx}", flush=True)
            _notify(f"Gerando estudo da F{idx}...")

            v = get_volume()
            t = get_temp_c()
            targets = parse_targets_from_fields(targets_fields)
            lines = list(output.lines or [])
            status = verificar_viabilidade_termodinamica(v, lines, insumos_cache, idx, temp_c=t)
            secoes = estudo_quimico.gerar_estudo_completo(idx, output, insumos_cache, targets, v, t)

            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text(f"ESTUDAR — F{idx}", weight=ft.FontWeight.BOLD),
                content=ft.Container(
                    content=estudo.build_study_view(secoes=list(secoes), status=status, output=output),
                    width=1100,
                    height=760,
                ),
                actions=[
                    ft.ElevatedButton("💾 Salvar como Relatório de Estudo (PDF)", bgcolor=ft.Colors.BLUE_900, color=ft.Colors.WHITE, on_click=lambda e=None, i=idx, ss=secoes: _save_estudo_report_pdf(i, ss)),
                    ft.TextButton("FECHAR", on_click=lambda e=None: _close_dialog()),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )

            def _close_dialog() -> None:
                dlg.open = False
                page.update()
                try:
                    if dlg in list(getattr(page, "overlay", []) or []):
                        page.overlay.remove(dlg)
                except Exception:
                    pass

            try:
                if dlg not in list(getattr(page, "overlay", []) or []):
                    page.overlay.append(dlg)
            except Exception:
                pass
            dlg.open = True
            page.update()
        except Exception as ex:
            import traceback
            print(f"Falha ao gerar/abrir estudo da F{idx}: {ex}\n{traceback.format_exc()}", flush=True)
            try:
                _notify(f"Falha ao abrir ESTUDAR: {ex}")
            except Exception:
                pass

>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
    def build_top12_formula_view(idx: int, output: FormulaOutput) -> ft.Control:
        try:
            v = get_volume()
            targets = parse_targets_from_fields(targets_fields)
            lines = output.lines
            status = verificar_viabilidade_termodinamica(v, lines, insumos_cache, idx, temp_c=get_temp_c())

            def build_risk_chart(output: FormulaOutput, volume_l: float) -> ft.Control:
                color_kps = "#EF5350"
                color_sat = "#FFA726"
                color_sal = "#42A5F5"
                color_ok = "#66BB6A"

                totals: Dict[str, float] = {}
                for l in output.lines:
                    for k, val in (l.contrib_pct or {}).items():
                        try:
                            fv = float(val or 0.0)
                        except Exception:
                            fv = 0.0
                        totals[str(k)] = float(totals.get(str(k), 0.0) or 0.0) + float(fv)

<<<<<<< HEAD
                # Punição Máxima para incompatibilidade química (Gesso/Empedramento)
=======
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
                triggered_pairs = motor._kps_triggered_pairs(totals, targets=None)
                has_quelante = any(
                    any(key in (l.insumo_nome or "").lower() for key in ("edta", "hbed", "dtpa", "hedta", "nta", "eddha", "quelant"))
                    for l in output.lines
                )
                pts_kps = 0 if has_quelante else (60 if triggered_pairs else 0)

<<<<<<< HEAD
                # Rigor extremo com Shelf-life (Risco de cristalização no inverno)
                sat = float(output.indice_saturacao or 0.0)
                pts_sat = 50 if sat >= 1.0 else (30 if sat >= 0.85 else 0)

                # Rigor com Viscosidade (Dificuldade de envase e bombeamento)
=======
                sat = float(output.indice_saturacao or 0.0)
                pts_sat = 50 if sat >= 1.0 else (30 if sat >= 0.85 else 0)

>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
                total_mass_kg = sum(float(getattr(l, "massa_kg", 0.0) or 0.0) for l in output.lines)
                carga_sais_pct_mv = (total_mass_kg / float(volume_l)) * 100.0 if volume_l > 0 else 0.0
                pts_sal = 20 if carga_sais_pct_mv >= 45.0 else (10 if carga_sais_pct_mv >= 35.0 else 0)

                total_pts = int(pts_kps + pts_sat + pts_sal)

                if total_pts <= 0:
                    radar = {"Seguro": 100.0, "KPS": 0.0, "Saturação": 0.0, "Salinidade": 0.0}
                else:
                    radar = {
                        "Seguro": 0.0,
                        "KPS": (float(pts_kps) / float(total_pts)) * 100.0,
                        "Saturação": (float(pts_sat) / float(total_pts)) * 100.0,
                        "Salinidade": (float(pts_sal) / float(total_pts)) * 100.0,
                    }

                parts: List[Tuple[str, float, str]] = [
                    ("KPS", float(radar.get("KPS") or 0.0), color_kps),
                    ("Saturação", float(radar.get("Saturação") or 0.0), color_sat),
                    ("Salinidade", float(radar.get("Salinidade") or 0.0), color_sal),
                    ("Seguro", float(radar.get("Seguro") or 0.0), color_ok),
                ]
<<<<<<< HEAD
                parts = [(n, v, c) for (n, v, c) in parts if v > 0.0]

                def _pct_to_flex(v: float) -> int:
                    return max(0, int(round(float(v) * 10.0)))

                bar_segments: List[ft.Control] = []
                for name, pct, color in parts:
=======
                parts = [(n, v2, c) for (n, v2, c) in parts if v2 > 0.0]

                def _pct_to_flex(vv: float) -> int:
                    return max(0, int(round(float(vv) * 10.0)))

                bar_segments: List[ft.Control] = []
                for _name, pct, color in parts:
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
                    bar_segments.append(
                        ft.Container(
                            expand=_pct_to_flex(pct),
                            height=18,
                            bgcolor=color,
                            border_radius=6,
                            alignment=ft.Alignment.CENTER,
                            content=ft.Text(f"{pct:.1f}%", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        )
                    )

                bar = ft.Container(
                    width=260,
                    content=ft.Row(bar_segments, spacing=2),
                    padding=6,
                    border=ft.border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.WHITE)),
                    border_radius=10,
                )

                def _legend_item(label: str, pct: float, color: str) -> ft.Control:
                    return ft.Row(
                        [
                            ft.Container(width=10, height=10, bgcolor=color, border_radius=2),
                            ft.Text(f"{label} ({pct:.1f}%)", size=10, weight=ft.FontWeight.W_500),
                        ],
                        spacing=6,
                    )

                legend = ft.Column([_legend_item(n, p, c) for (n, p, c) in parts], spacing=2, tight=True)

                return ft.Container(
                    content=ft.Row([bar, legend], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor=ft.Colors.with_opacity(0.8, "#1A1C1E"),
                    padding=15,
<<<<<<< HEAD
                    border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
=======
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
                    border_radius=15,
                    blur=ft.Blur(10, 10),
                )

<<<<<<< HEAD
=======
            alerta_ui = build_thermo_alert(status)
            viability_ui = build_viability_card(lines, v, status.tech_tier, aditivos_cache, status)
            tabela_ui = build_data_table(lines, insumos_cache, v, targets, bool(supply_chain_switch.value), page=page)
            riscos_ui = build_risk_chart(output, v)

>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
            recomendacoes_ui = build_recommendations_view(
                output.process_steps,
                output.aditivos_sugeridos,
                lines,
<<<<<<< HEAD
                instrucoes_producao=(),
            )
            roteiro_ui = build_production_roadmap(output.instrucoes_producao)

            pred = {}
            try:
                if output.instrucoes_producao and isinstance(output.instrucoes_producao[0], dict):
                    p = output.instrucoes_producao[0].get("predicoes")
                    if isinstance(p, dict):
                        pred = p
            except Exception:
                pred = {}

            if not pred:
                ph_est = motor._estimate_ph_theoretical(lines, v)
                thermal = motor._thermal_balance_estimate(lines, insumos_cache, v, float(get_temp_c() or 25.0))
                mix_min = motor._estimate_mix_time_min(lines, insumos_cache, v)
                ionic = motor._estimate_ionic_strength(lines, v, ph_est=ph_est)
                sat_local = float(output.indice_saturacao or 0.0)
                sc_mode = sat_local > 1.10
                dens = float((thermal or {}).get("densidade") or (motor._estimated_density(lines, insumos_cache, v) or 1.0))
                evap = motor._estimate_evap_loss_kg(v, dens, float(60.0 if idx >= 9 else get_temp_c()), float(mix_min or 30.0))
                pred = {
                    "ph_est": ph_est,
                    "temp_out_c": None if not thermal else thermal.get("temp_out_c"),
                    "delta_t_c": None if not thermal else thermal.get("delta_t_c"),
                    "mix_time_min": float(mix_min or 0.0),
                    "evap_loss_kg": float(evap or 0.0),
                    "ionic_strength": float(ionic or 0.0),
                    "reologia": ("Não-Newtoniano" if sc_mode else "Newtoniano"),
                    "sc_mode": bool(sc_mode),
                }

            phv = pred.get("ph_est")
            tout = pred.get("temp_out_c")
            dt = pred.get("delta_t_c")
            mixm = pred.get("mix_time_min")
            evapk = pred.get("evap_loss_kg")
            ionic = pred.get("ionic_strength")
            rheo = pred.get("reologia")

            ok_ph = (phv is None) or (float(phv) >= 3.0 and float(phv) <= 7.0)
            ok_t = (tout is None) or (float(tout) >= 15.0)
            ok = bool(ok_ph and ok_t)

            icon = ft.Icons.CHECK_CIRCLE if ok else ft.Icons.WARNING_AMBER
            color = ft.Colors.GREEN_400 if ok else ft.Colors.AMBER_400

            def _fmt(vv: Any, fmt: str) -> str:
                if vv is None:
                    return "-"
                try:
                    return fmt.format(float(vv))
                except Exception:
                    return str(vv)

            lab_panel = ft.Container(
                padding=12,
                border=ft.border.all(1, ft.Colors.with_opacity(0.22, ft.Colors.WHITE)),
                border_radius=12,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.BLUE_GREY_900),
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(icon, color=color, size=18),
                                ft.Text("Painel de Predição Físico-Química", size=12, weight=ft.FontWeight.BOLD),
                            ],
                            spacing=8,
                        ),
                        ft.Row(
                            [
                                ft.Text(f"pH teórico: {_fmt(phv, '{:.1f}')}", size=11),
                                ft.Text(f"T final: {_fmt(tout, '{:.1f}')}°C", size=11),
                                ft.Text(f"ΔT: {_fmt(dt, '{:+.1f}')}°C", size=11),
                            ],
                            wrap=True,
                            spacing=14,
                        ),
                        ft.Row(
                            [
                                ft.Text(f"Tempo de mistura: {_fmt(mixm, '{:.0f}')} min", size=11),
                                ft.Text(f"Evaporação estimada: {_fmt(evapk, '{:.2f}')} kg", size=11),
                                ft.Text(f"Força iônica I: {_fmt(ionic, '{:.3f}')} mol/L", size=11),
                            ],
                            wrap=True,
                            spacing=14,
                        ),
                        ft.Row(
                            [
                                ft.Text(f"Perfil reológico: {str(rheo or '-')}", size=11),
                            ],
                            wrap=True,
                            spacing=14,
                        ),
                    ],
                    spacing=6,
                ),
            )

            return ft.Stack(
                [
                    ft.Column(
                        controls=[
                            build_thermo_alert(status),
                            build_data_table(lines, insumos_cache, v, targets, bool(supply_chain_switch.value), page=page),
                            lab_panel,
                            roteiro_ui,
                            ft.ElevatedButton(
                                "SELECIONAR P/ PDF",
                                icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
                                on_click=lambda _, l=lines, i=idx: _select_formula_for_report(l, i, open_report_tab=False),
                            ),
                            ft.ElevatedButton(
                                "ENVIAR PARA LAUDO / OP",
                                icon=ft.Icons.FILE_DOWNLOAD,
                                on_click=lambda _, l=lines, i=idx: on_send_to_laudo(l, i),
                            ),
                            recomendacoes_ui,
                            ft.Container(height=100),
                        ],
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                    ),
                    ft.Container(
                        content=build_risk_chart(output, v),
                        right=20,
                        bottom=20,
                    ),
                ],
                expand=True,
            )

        except Exception as e:
            return ft.Container(content=ft.Text(f"Erro: {str(e)}", color=ft.Colors.RED_400))
=======
                instrucoes_producao=output.instrucoes_producao,
            )
            roteiro_ui = build_production_roadmap(output.instrucoes_producao)

            btn_laudo = ft.Button(
                content="ENVIAR PARA LAUDO / OP",
                icon=ft.Icons.FILE_DOWNLOAD,
                on_click=lambda _e=None, l=lines, i=idx: on_send_to_laudo(l, i),
                style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_900, color=ft.Colors.WHITE),
            )
            btn_estudar = ft.Button(
                content="ESTUDAR",
                icon=ft.Icons.SCHOOL,
                on_click=lambda _e=None, i=idx, o=output: _open_estudo_dialog(i, o),
                style=ft.ButtonStyle(bgcolor=ft.Colors.PURPLE_800, color=ft.Colors.WHITE),
            )

            return ft.Container(
                content=ft.Column(
                    [
                        alerta_ui,
                        ft.Row([viability_ui, riscos_ui], wrap=True, spacing=12),
                        tabela_ui,
                        ft.Row([btn_laudo, btn_estudar], wrap=True, spacing=10),
                        ft.Divider(),
                        roteiro_ui,
                        ft.Divider(),
                        recomendacoes_ui,
                    ],
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                    spacing=10,
                ),
                padding=10,
                expand=True,
            )
        except Exception as e:
            import traceback
            print(f"Erro ao renderizar a fórmula {idx}: {e}", flush=True)
            traceback.print_exc()
            return ft.Container(content=ft.Text(f"Erro na fórmula {idx}: {str(e)}", color=ft.Colors.RED_400, weight=ft.FontWeight.BOLD), padding=20)
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c

    def build_top12_tabs(forms: List[FormulaOutput]) -> None:
        labels = []
        views = []
<<<<<<< HEAD
        
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

    def _select_formula_for_report(lines, idx, *, open_report_tab: bool) -> None:
        nonlocal current_relatorio
        v = get_volume()
        t = get_temp_c()
        targets = parse_targets_from_fields(targets_fields)
        status = verificar_viabilidade_termodinamica(v, lines, insumos_cache, idx, temp_c=t)
        lines_copy = list(lines)
        ph_est = motor._estimate_ph_theoretical(lines_copy, v)
        steps, ad_sug = recommend_process_and_aditivos(
            targets,
            lines_copy,
            aditivos_cache,
            insumos_cache,
            v,
            t,
            ph_estimated=ph_est,
            formula_index=idx,
            reactor_level_available=get_reactor_level(),
        )
        roteiro = diagnosticar_operacoes_unitarias(
            lines_copy,
            insumos_cache,
            ad_sug,
            v,
            t,
            formula_index=idx,
        )
        if roteiro:
            head = roteiro[0]
            pop_lines = list(head.get("pop") or [])
            for s in steps:
                pop_lines.append(str(s))
            for sug in (ad_sug or []):
                a = sug.aditivo
                nm = f"{a.nome} ({a.abreviatura})" if a.abreviatura else a.nome
                pop_lines.append(f"Aditivo: {nm} | Dose: {sug.dose_recomendada_pct_texto} ({sug.dose_recomendada_massa_texto}) | Motivo: {sug.motivo}")
            head["pop"] = pop_lines
            roteiro[0] = head

        rel = gerar_relatorio_op(lines_copy, v, status)
=======
        for i, f in enumerate(forms or []):
            idx = i + 1
            if idx <= 4:
                label = f"F{idx} (Tier 1 - Conservador)"
            elif idx <= 8:
                label = f"F{idx} (Tier 2 - Audacioso / exploratório)"
            else:
                label = f"F{idx} (Tier 3 - Alquimia / não ortodoxo)"
            labels.append(label)
            views.append(build_top12_formula_view(idx, f))
        set_tabs(top12_tabs, labels, views)
        page.update()

    def _select_formula_for_report(lines: Sequence[FormulaLine], idx: int, *, open_report_tab: bool = True) -> None:
        nonlocal current_relatorio
        v = get_volume()
        status = verificar_viabilidade_termodinamica(v, list(lines), insumos_cache, idx, temp_c=get_temp_c())
        roteiro = diagnosticar_operacoes_unitarias(list(lines), insumos_cache, [], v, get_temp_c(), formula_index=idx)
        rel = gerar_relatorio_op(list(lines), v, status)
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
        rel.titulo = f"F{idx} — {rel.titulo}"
        if roteiro:
            rel.pop_etapas = list(roteiro)
            uniq: List[Dict[str, str]] = []
            seen = set()
            for st in roteiro:
                for p in (st.get("pccs") or []):
                    if not isinstance(p, dict):
                        continue
                    key = (str(p.get("id") or ""), str(p.get("parametro") or ""), str(p.get("limite") or ""), str(p.get("acao") or ""))
                    if key in seen:
                        continue
                    seen.add(key)
                    uniq.append(dict(p))
            rel.pcc_pontos = uniq
        current_relatorio = rel
        update_laudo_document(rel)
        if open_report_tab:
            main_tabs.selected_index = 2
            page.snack_bar = ft.SnackBar(ft.Text(f"F{idx} carregada em Relatório & POP."))
<<<<<<< HEAD
        else:
            page.snack_bar = ft.SnackBar(ft.Text(f"F{idx} selecionada para PDF (Relatório & POP)."))
        page.snack_bar.open = True
=======
            page.snack_bar.open = True
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
        page.update()

    def on_send_to_laudo(lines, idx):
        _select_formula_for_report(lines, idx, open_report_tab=True)

    def update_laudo_document(rel: RelatorioOP):
        laudo_content.controls.clear()
        targets = parse_targets_from_fields(targets_fields)
        targets_rows = []
        for k, label in NUTRIENT_COLUMNS:
            v = float(targets.get(k, 0.0) or 0.0)
            if v <= 0:
                continue
            targets_rows.append(ft.DataRow([ft.DataCell(ft.Text(label, color=ft.Colors.BLACK)), ft.DataCell(ft.Text(f"{v:.3f}", color=ft.Colors.BLACK))]))

        roteiro_controls: List[ft.Control] = []
        etapas = rel.pop_etapas or []
        if etapas and isinstance(etapas[0], dict) and ("nome_etapa" in etapas[0]):
            roteiro_controls.append(ft.Text("\nROTEIRO DE PRODUÇÃO INDUSTRIAL (RITMO/ETAPAS)", weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK))
<<<<<<< HEAD
            prev_border_color: Optional[str] = None

            def _pick_border_color(stage_name: str, idx: int) -> str:
                name = (stage_name or "").casefold()
                if "prepar" in name or "matriz" in name:
                    base = ft.Colors.CYAN_700
                elif "complex" in name:
                    base = ft.Colors.PURPLE_700
                elif "dissol" in name or "satura" in name:
                    base = ft.Colors.ORANGE_800
                elif "micro" in name:
                    base = ft.Colors.TEAL_700
                elif "final" in name:
                    base = ft.Colors.GREEN_700
                else:
                    base = ft.Colors.BLUE_GREY_700

                palette = [
                    base,
                    ft.Colors.BLUE_700,
                    ft.Colors.INDIGO_700,
                    ft.Colors.PINK_700,
                    ft.Colors.AMBER_800,
                    ft.Colors.BROWN_700,
                ]
                if prev_border_color is None:
                    return palette[0]
                for c in palette:
                    if c != prev_border_color:
                        return c
                return palette[(idx - 1) % len(palette)]

=======
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
            for i, st in enumerate(etapas, start=1):
                nome = str(st.get("nome_etapa") or f"Etapa {i}")
                instr = str(st.get("instrucao_processo") or "")
                tempo = str(st.get("tempo") or "")
                pm = st.get("parametros_maquina") or {}
                rpm = pm.get("rpm")
                tc = pm.get("temp_c")
                meta_bits = []
                if rpm is not None and str(rpm).strip():
                    meta_bits.append(f"RPM: {rpm}")
                if tc is not None and str(tc).strip():
                    try:
                        meta_bits.append(f"T: {float(tc):.1f}°C")
                    except Exception:
                        meta_bits.append(f"T: {tc}")
                if tempo:
                    meta_bits.append(f"Tempo: {tempo}")
                meta = " | ".join(meta_bits)
                gate = st.get("gate_ph") or {}
                gate_txt = str(gate.get("texto") or "").strip()
                pop_lines = st.get("pop") or []
                pccs = st.get("pccs") or []

<<<<<<< HEAD
                border_color = _pick_border_color(nome, i)
                prev_border_color = border_color
                header_bg = ft.Colors.with_opacity(0.12, border_color)

                bloco: List[ft.Control] = []
                bloco.append(
                    ft.Container(
                        bgcolor=header_bg,
                        padding=ft.padding.symmetric(horizontal=8, vertical=6),
                        content=ft.Text(f"{i}. {nome}", weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK, size=12),
                    )
                )
                if instr:
                    bloco.append(ft.Text(instr, color=ft.Colors.BLACK87, size=11))

                def _pv_row(label: str, value: str) -> ft.Control:
                    return ft.Row(
                        [
                            ft.Container(
                                width=120,
                                content=ft.Text(label, color=ft.Colors.BLACK, size=10, weight=ft.FontWeight.BOLD),
                            ),
                            ft.Container(
                                expand=True,
                                content=ft.Text(value, color=ft.Colors.BLACK87, size=10),
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )

                pv_lines: List[ft.Control] = []
                if rpm is not None and str(rpm).strip():
                    pv_lines.append(_pv_row("RPM", str(rpm)))
                    pv_lines.append(ft.Divider(height=1, color=ft.Colors.BLACK12))
                if tc is not None and str(tc).strip():
                    try:
                        pv_lines.append(_pv_row("Temperatura", f"{float(tc):.1f} °C"))
                    except Exception:
                        pv_lines.append(_pv_row("Temperatura", str(tc)))
                    pv_lines.append(ft.Divider(height=1, color=ft.Colors.BLACK12))
                if tempo:
                    pv_lines.append(_pv_row("Tempo", str(tempo)))
                    pv_lines.append(ft.Divider(height=1, color=ft.Colors.BLACK12))
                if pv_lines:
                    pv_lines.pop()
                else:
                    pv_lines.append(_pv_row("Parâmetros", "-"))

                bloco.append(
                    ft.Container(
                        bgcolor=ft.Colors.with_opacity(0.04, border_color),
                        padding=10,
                        border=ft.border.all(1, ft.Colors.with_opacity(0.20, border_color)),
                        border_radius=8,
                        content=ft.Column(pv_lines, spacing=0),
                    )
                )

                if gate_txt:
                    bloco.append(ft.Text(gate_txt, color=ft.Colors.RED_900, size=11, weight=ft.FontWeight.BOLD))

=======
                bloco: List[ft.Control] = []
                bloco.append(ft.Text(f"{i}. {nome}", weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK, size=12))
                if instr:
                    bloco.append(ft.Text(instr, color=ft.Colors.BLACK87, size=11))
                if meta:
                    bloco.append(ft.Text(meta, color=ft.Colors.BLACK54, size=10))
                if gate_txt:
                    bloco.append(ft.Text(gate_txt, color=ft.Colors.RED_900, size=11, weight=ft.FontWeight.BOLD))
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
                if pop_lines:
                    bloco.append(ft.Text("POP", color=ft.Colors.BLACK, size=10, weight=ft.FontWeight.BOLD))
                    for ln in pop_lines[:6]:
                        bloco.append(ft.Text(f"- {ln}", color=ft.Colors.BLACK87, size=10))
<<<<<<< HEAD

                if pccs:
                    bloco.append(ft.Text("PCC", color=ft.Colors.BLACK, size=10, weight=ft.FontWeight.BOLD))
                    for p in pccs[:6]:
=======
                if pccs:
                    bloco.append(ft.Text("PCC", color=ft.Colors.BLACK, size=10, weight=ft.FontWeight.BOLD))
                    for p in pccs[:6]:
                        if not isinstance(p, dict):
                            continue
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
                        pid = str(p.get("id") or "").strip()
                        par = str(p.get("parametro") or "").strip()
                        lim = str(p.get("limite") or "").strip()
                        acao = str(p.get("acao") or "").strip()
                        txt = f"{pid} — {par}: {lim} -> {acao}" if pid else f"{par}: {lim} -> {acao}"
                        bloco.append(ft.Text(f"- {txt}", color=ft.Colors.BLACK87, size=10))

<<<<<<< HEAD
                roteiro_controls.append(
                    ft.Container(
                        content=ft.Column(bloco, spacing=6),
                        padding=15,
                        border=ft.Border.all(2, border_color),
                        border_radius=8,
                        margin=ft.margin.only(bottom=10),
                    )
                )
        else:
            roteiro_controls.append(ft.Text("\nPROCEDIMENTO OPERACIONAL (POP)", weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK))
            roteiro_controls.append(ft.Column([ft.Text(f"• {e['etapa']}: {e['procedimento']} ({e['notas']})", color=ft.Colors.BLACK87, size=12) for e in rel.pop_etapas]))

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
                ft.Text(rel.titulo, size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK, text_align=ft.TextAlign.CENTER),
                ft.Text(f"Volume Final: {get_volume()} L | Temperatura: {format_num(get_temp_c(), 1)}°C | Reator: {reactor_dd.value}", color=ft.Colors.BLACK87),
                ft.Text(f"Densidade: {format_num(rel.densidade, 3)} kg/L | Balanço Hídrico: {format_num(rel.agua_balanco, 2)} kg", color=ft.Colors.BLACK87),
                ft.Text("\nALVOS (TÍTULO)", weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
                ft.DataTable(
                    columns=[ft.DataColumn(ft.Text("Nutriente", color=ft.Colors.BLACK)), ft.DataColumn(ft.Text("%", color=ft.Colors.BLACK))],
                    rows=targets_rows if targets_rows else [ft.DataRow([ft.DataCell(ft.Text("-", color=ft.Colors.BLACK54)), ft.DataCell(ft.Text("-", color=ft.Colors.BLACK54))])],
                ),
                ft.Text("\nCOMPOSIÇÃO DE CARGA (BOM)", weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
                ft.DataTable(
                    columns=[ft.DataColumn(ft.Text("Insumo", color=ft.Colors.BLACK)), ft.DataColumn(ft.Text("Massa (kg)", color=ft.Colors.BLACK))],
                    rows=[ft.DataRow([ft.DataCell(ft.Text(l.insumo_nome, color=ft.Colors.BLACK)), ft.DataCell(ft.Text(format_num(l.massa_kg, 3), color=ft.Colors.BLACK))]) for l in rel.bom_lines],
                    data_row_min_height=40,
                    data_row_max_height=60,
                    heading_row_height=45,
                ),
                *roteiro_controls,
                ft.Text("\nPONTOS CRÍTICOS DE CONTROLE (PCC)", weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
                ft.Column([ft.Text(f"! {p['parametro']}: {p['limite']} -> {p['acao']}", color=ft.Colors.BLACK87, size=11) for p in rel.pcc_pontos]),
                ft.Text("\nCHECKLIST DE LIBERAÇÃO (A4)", weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
                ft.Column([
                    ft.Text("□ Aparência homogênea (sem grumos/cristais visíveis)", color=ft.Colors.BLACK87, size=11),
                    ft.Text("□ pH final registrado (alvo conforme TDS)", color=ft.Colors.BLACK87, size=11),
                    ft.Text("□ Densidade registrada", color=ft.Colors.BLACK87, size=11),
                    ft.Text("□ Filtrabilidade / bico ok (se aplicável)", color=ft.Colors.BLACK87, size=11),
                    ft.Text("□ Amostra retida e identificada", color=ft.Colors.BLACK87, size=11),
                ], spacing=2),
                ft.Text("\nREGISTRO DO LOTE", weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
                ft.Row([
                    ft.Text("Lote: ____________________", color=ft.Colors.BLACK87, size=11),
                    ft.Text("Data: ____/____/______", color=ft.Colors.BLACK87, size=11),
                    ft.Text("Responsável: ____________________", color=ft.Colors.BLACK87, size=11),
                ], wrap=True),
                ft.Text("Assinatura: _________________________________________________", color=ft.Colors.BLACK87, size=11),
            ])
=======
                roteiro_controls.append(ft.Container(content=ft.Column(bloco, spacing=6), padding=12, border=ft.Border.all(1, ft.Colors.BLACK12), border_radius=8, margin=ft.margin.only(bottom=10)))
        else:
            roteiro_controls.append(ft.Text("\nPROCEDIMENTO OPERACIONAL (POP)", weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK))
            roteiro_controls.append(ft.Column([ft.Text(f"• {e['etapa']}: {e['procedimento']} ({e['notas']})", color=ft.Colors.BLACK87, size=12) for e in (rel.pop_etapas or []) if isinstance(e, dict)]))

        a4 = ft.Container(
            bgcolor=ft.Colors.WHITE,
            padding=50,
            width=800,
            border_radius=2,
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.BLACK54),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text("ORION AGROQUIM", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
                            ft.Column(
                                [
                                    ft.Text(f"DATA: {rel.data_hora}", color=ft.Colors.BLACK, size=10),
                                    ft.Text(f"TIER: {rel.tier}", color=ft.Colors.BLACK, size=10),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.END,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(color=ft.Colors.BLACK26),
                    ft.Text(rel.titulo, size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK, text_align=ft.TextAlign.CENTER),
                    ft.Text(f"Volume Final: {get_volume()} L | Temperatura: {format_num(get_temp_c(), 1)}°C | Reator: {reactor_dd.value}", color=ft.Colors.BLACK87),
                    ft.Text(f"Densidade: {format_num(rel.densidade, 3)} kg/L | Balanço Hídrico: {format_num(rel.agua_balanco, 2)} kg", color=ft.Colors.BLACK87),
                    ft.Text("\nALVOS (TÍTULO)", weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
                    ft.DataTable(
                        columns=[ft.DataColumn(ft.Text("Nutriente", color=ft.Colors.BLACK)), ft.DataColumn(ft.Text("%", color=ft.Colors.BLACK))],
                        rows=targets_rows if targets_rows else [ft.DataRow([ft.DataCell(ft.Text("-", color=ft.Colors.BLACK54)), ft.DataCell(ft.Text("-", color=ft.Colors.BLACK54))])],
                    ),
                    ft.Text("\nCOMPOSIÇÃO DE CARGA (BOM)", weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
                    ft.DataTable(
                        columns=[ft.DataColumn(ft.Text("Insumo", color=ft.Colors.BLACK)), ft.DataColumn(ft.Text("Massa (kg)", color=ft.Colors.BLACK))],
                        rows=[ft.DataRow([ft.DataCell(ft.Text(l.insumo_nome, color=ft.Colors.BLACK)), ft.DataCell(ft.Text(format_num(l.massa_kg, 3), color=ft.Colors.BLACK))]) for l in (rel.bom_lines or [])],
                        data_row_min_height=40,
                        data_row_max_height=60,
                        heading_row_height=45,
                    ),
                    *roteiro_controls,
                    ft.Text("\nPONTOS CRÍTICOS DE CONTROLE (PCC)", weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
                    ft.Column([ft.Text(f"! {p.get('parametro','')}: {p.get('limite','')} -> {p.get('acao','')}", color=ft.Colors.BLACK87, size=11) for p in (rel.pcc_pontos or []) if isinstance(p, dict)]),
                ],
                spacing=6,
            ),
>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
        )
        laudo_content.controls.append(ft.Row([a4], alignment=ft.MainAxisAlignment.CENTER))
        page.update()

    page.add(header, main_tabs)
    reload_data()

<<<<<<< HEAD
=======

>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
def main(page: ft.Page) -> None:
    try:
        _main_impl(page)
    except Exception:
        import traceback
        err = traceback.format_exc()
        print(f"[ERRO FATAL]\n{err}", flush=True)
        _write_error_log(err)
        page.add(ft.Text("Erro fatal. Verifique orionagroquim_error.log"))

<<<<<<< HEAD
=======

>>>>>>> cdbd2873ca1611d6c916c4d9a1269efe9d6f0d6c
if __name__ == "__main__":
    ft.run(main)
