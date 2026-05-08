from __future__ import annotations

from typing import Any, List, Optional

import flet as ft

from estudo_quimico import SecaoEstudo


def build_study_view(
    *,
    secoes: List[SecaoEstudo],
    status: Any = None,
    output: Any = None,
) -> ft.Control:
    blocks: List[ft.Control] = []
    for s in list(secoes or []):
        title = ft.Text(str(s.titulo or ""), size=14, weight=ft.FontWeight.BOLD)

        alert_txt = str(s.alerta or "").strip()
        reco_txt = str(s.recomendacao or "").strip()
        quim_txt = str(s.quimica or "").strip()
        mat_txt = str(s.matematica or "").strip()
        log_txt = str(s.logica or "").strip()
        py_txt = str(s.python or "").strip()

        alert = ft.Container()
        if alert_txt:
            alert = ft.Container(
                content=ft.Text(alert_txt, size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_300),
                bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.RED_400),
                padding=10,
                border_radius=10,
            )

        reco = ft.Container()
        if reco_txt:
            reco = ft.Container(
                content=ft.Text(reco_txt, size=12, weight=ft.FontWeight.W_500, color=ft.Colors.WHITE),
                bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.GREEN_400),
                padding=10,
                border_radius=10,
            )

        internos: List[ft.Control] = []
        if quim_txt:
            internos.append(ft.Text(quim_txt, size=13, color=ft.Colors.WHITE))

        if mat_txt:
            internos.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text("📐 Matemática", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            ft.Text(mat_txt, color=ft.Colors.CYAN_300, size=15, font_family="monospace"),
                        ],
                        spacing=6,
                    ),
                    padding=10,
                    bgcolor=ft.Colors.BLACK,
                    border_radius=8,
                    border=ft.Border.all(1, ft.Colors.CYAN_900),
                )
            )

        if log_txt:
            internos.append(ft.Text("💡 Lógica", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE))
            internos.append(ft.Text(log_txt, color=ft.Colors.with_opacity(0.7, ft.Colors.WHITE), size=12, italic=True))

        if py_txt:
            internos.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text("🐍 Python", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            ft.Text(py_txt, color=ft.Colors.GREEN_400, size=13, font_family="monospace"),
                        ],
                        spacing=6,
                    ),
                    padding=10,
                    bgcolor="#0A0A0A",
                    border_radius=8,
                    border=ft.Border.all(1, ft.Colors.GREEN_900),
                )
            )

        blocks.append(
            ft.Container(
                content=ft.Column([title, alert, reco, ft.Column(internos, spacing=10)], spacing=8),
                padding=12,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.WHITE)),
                border_radius=12,
            )
        )

    return ft.Container(
        content=ft.Column(blocks, spacing=10, scroll=ft.ScrollMode.AUTO, expand=True),
        expand=True,
    )
