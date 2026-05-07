from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import uuid

import flet as ft

from motor import KPS_PARES_PROIBIDOS


@dataclass(frozen=True)
class StabilityAck:
    ok: bool
    message: str
    record_id: str
    received_at: str


@dataclass
class StabilityRecord:
    id: str
    received_at: str
    payload: Dict[str, Any]
    summary: Dict[str, Any]


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        return f if f == f else None
    except Exception:
        return None


def _totals_from_serialized_lines(lines: Sequence[Dict[str, Any]]) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    for l in lines:
        contrib = l.get("contrib_pct") or {}
        if not isinstance(contrib, dict):
            continue
        for k, v in contrib.items():
            fv = _safe_float(v)
            if fv is None:
                continue
            totals[str(k)] = float(totals.get(str(k), 0.0) or 0.0) + float(fv)
    return totals


def _kps_triggered_pairs(totals: Dict[str, float], targets: Optional[Dict[str, float]] = None) -> List[Tuple[str, str]]:
    def present(k: str) -> bool:
        tv = float(totals.get(k, 0.0) or 0.0)
        gv = float((targets or {}).get(k, 0.0) or 0.0)
        return tv > 0.0 or gv > 0.0

    triggered: List[Tuple[str, str]] = []
    for (a, b), _meta in KPS_PARES_PROIBIDOS.items():
        if present(str(a)) and present(str(b)):
            triggered.append((str(a), str(b)))
    return triggered


def _protocol_plan_controls() -> ft.Control:
    steps = [
        "Caracterizar água (pH, EC, dureza Ca/Mg, alcalinidade, turbidez).",
        "T0 em triplicata (água real) + triplicata (DI): foto, pH/EC, escoamento, filtrabilidade, redispersão 24h.",
        "Acelerados: 25°C estático; 25°C + vibração diária; ciclo 15↔35°C + vibração leve (D0/D1/D3/D7/D14/D28).",
        "Se aparecer sólido: microscopia óptica (e polarizada se disponível) + testes simples de solubilidade (25°C, 40°C, pH 4–5, pH 8–9).",
        "Se disponível: XRD/FTIR/Raman/SEM-EDS para identificar fase e orientar prevenção.",
        "Aceitação: sem cristal visível; sem caking; passa em malha/bico; redispersa em 10 inversões/30s.",
    ]
    return ft.Container(
        content=ft.Column(
            [ft.Text("Protocolo de Estabilidade (Resumo)", size=14, weight=ft.FontWeight.BOLD)]
            + [ft.Text(f"- {s}", size=12) for s in steps],
            spacing=6,
        ),
        padding=10,
        border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
        border_radius=10,
    )


class StabilityModule:
    def __init__(self, *, page: Optional[ft.Page] = None) -> None:
        self._page = page
        self._records: List[StabilityRecord] = []
        self._status_text = ft.Text("Aguardando resultados do motor…", size=12, italic=True)
        self._risk_bar = ft.Container(
            content=ft.Text("Sem dados para avaliar risco.", size=12, italic=True),
            padding=10,
            border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
            border_radius=10,
        )
        self._list = ft.ListView(expand=True, spacing=4, auto_scroll=False)
        self._details = ft.Container(
            content=ft.Text("Selecione um item para ver detalhes.", size=12),
            padding=10,
            border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
            border_radius=10,
            expand=True,
        )

        self.view = ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.SCIENCE, color=ft.Colors.BLUE_400),
                        ft.Text("Estabilidade", size=18, weight=ft.FontWeight.BOLD),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                ),
                self._status_text,
                self._risk_bar,
                _protocol_plan_controls(),
                ft.Divider(),
                ft.Row(
                    [
                        ft.Container(content=self._list, width=480, padding=0, expand=False),
                        ft.Container(content=self._details, expand=True),
                    ],
                    expand=True,
                ),
            ],
            expand=True,
            spacing=10,
        )

    def ingest_calc_results(self, payload: Dict[str, Any]) -> StabilityAck:
        try:
            err = self._validate_payload(payload)
            if err:
                ack = StabilityAck(False, err, "", _now_iso())
                self._set_status(ack)
                return ack

            summary = self._summarize_payload(payload)
            rec_id = str(uuid.uuid4())
            payload.setdefault("lab", {"ph": None, "ec": None, "turbidez": None, "observacoes": ""})
            rec = StabilityRecord(rec_id, _now_iso(), payload, summary)
            self._records.insert(0, rec)
            ack = StabilityAck(True, "Recebido e processado.", rec_id, rec.received_at)
            self._render_list()
            self._render_details(rec_id)
            self._update_risk_bar(rec.summary)
            self._set_status(ack)
            return ack
        except Exception as e:
            ack = StabilityAck(False, f"Falha ao processar: {str(e)}", "", _now_iso())
            self._set_status(ack)
            return ack

    def reset(self) -> None:
        self._records.clear()
        self._status_text.value = "Aguardando resultados do motor…"
        self._status_text.color = ft.Colors.with_opacity(0.85, ft.Colors.WHITE)
        self._risk_bar.content = ft.Text("Sem dados para avaliar risco.", size=12, italic=True)
        self._risk_bar.border = ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE))
        self._risk_bar.bgcolor = None
        self._list.controls.clear()
        self._details.content = ft.Text("Selecione um item para ver detalhes.", size=12)
        if self._page:
            self._page.update()

    def last_snapshot(self) -> Optional[Dict[str, Any]]:
        if not self._records:
            return None
        rec = self._records[0]
        lab = rec.payload.get("lab") if isinstance(rec.payload, dict) else None
        return {"summary": rec.summary or {}, "lab": (lab if isinstance(lab, dict) else {})}

    def _set_status(self, ack: StabilityAck) -> None:
        if ack.ok:
            self._status_text.value = f"Última recepção: OK ({ack.received_at}) | id={ack.record_id}"
            self._status_text.color = ft.Colors.GREEN_400
        else:
            self._status_text.value = f"Última recepção: ERRO ({ack.received_at}) | {ack.message}"
            self._status_text.color = ft.Colors.RED_400
        if self._page:
            self._page.update()

    def _validate_payload(self, payload: Dict[str, Any]) -> Optional[str]:
        if not isinstance(payload, dict):
            return "Payload inválido (não é dict)."
        if payload.get("kind") != "calc_run":
            return "Payload inválido (kind != calc_run)."
        volume_l = _safe_float(payload.get("volume_l"))
        if volume_l is None or not (volume_l > 0):
            return "Payload inválido (volume_l ausente/inválido)."
        temp_c = _safe_float(payload.get("temp_c"))
        if temp_c is None:
            return "Payload inválido (temp_c ausente/inválido)."
        targets = payload.get("targets")
        if targets is None or not isinstance(targets, dict):
            return "Payload inválido (targets ausente/inválido)."
        outputs = payload.get("outputs")
        if outputs is None or not isinstance(outputs, list) or not outputs:
            return "Payload inválido (outputs ausente/inválido)."
        for o in outputs:
            if not isinstance(o, dict):
                return "Payload inválido (output não é dict)."
            if "idx" not in o:
                return "Payload inválido (output.idx ausente)."
            lines = o.get("lines")
            if lines is None or not isinstance(lines, list):
                return "Payload inválido (output.lines ausente/inválido)."
        return None

    def _summarize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        outputs = payload.get("outputs") or []
        best = outputs[0] if outputs else {}
        best_lines = best.get("lines") or []
        totals = _totals_from_serialized_lines(best_lines)

        volume_l = float(payload.get("volume_l") or 0.0)
        total_mass_kg = sum(float(_safe_float(l.get("massa_kg")) or 0.0) for l in best_lines)
        carga_sais_pct_mv = (total_mass_kg / volume_l) * 100.0 if volume_l > 0 else 0.0

        targets = payload.get("targets") or {}
        triggered_pairs = _kps_triggered_pairs(totals, targets=targets)

        alerts: List[str] = []
        if carga_sais_pct_mv >= 40.0:
            alerts.append(f"Carga salina alta: {carga_sais_pct_mv:.1f}% (m/v).")
        n = float(totals.get("N", 0.0) or 0.0)
        if n >= 20.0:
            alerts.append(f"N alto: {n:.2f}% (m/v) → risco de supersaturação/cristalização.")
        if triggered_pairs:
            alerts.append(f"Pares críticos: {triggered_pairs}")

        sat = _safe_float(best.get("indice_saturacao"))
        if sat is not None and sat >= 1.0:
            alerts.append(f"Índice de saturação >= 1.0 ({sat:.3f}) → risco de cristalização.")

        aditivos = best.get("aditivos_sugeridos") or []
        has_quelante = False
        preferred = {"EDTA", "HEDTA", "DTPA", "NTA"}
        for a in aditivos:
            abbr = str((a or {}).get("abreviatura") or "").strip().upper()
            grp = str((a or {}).get("grupo") or "").strip().lower()
            func = str((a or {}).get("funcao_principal") or "").strip().lower()
            if abbr in preferred or "quelant" in grp or "quelant" in func:
                has_quelante = True
                break
        if not has_quelante:
            for l in best_lines:
                nm = str((l or {}).get("insumo_nome") or "").strip().lower()
                if any(x.lower() in nm for x in ("edta", "hedta", "dtpa", "nta", "quelant")):
                    has_quelante = True
                    break

        risk, risk_reasons = self._risk_from_metrics(
            carga_sais_pct_mv=carga_sais_pct_mv,
            indice_saturacao=sat,
            triggered_pairs=triggered_pairs,
            totals=totals,
            has_quelante=has_quelante,
        )

        return {
            "received_at": payload.get("timestamp") or "",
            "volume_l": volume_l,
            "temp_c": float(payload.get("temp_c") or 0.0),
            "targets": dict(targets),
            "best_idx": best.get("idx"),
            "best_totals": totals,
            "best_total_mass_kg": total_mass_kg,
            "best_carga_sais_pct_mv": carga_sais_pct_mv,
            "best_indice_saturacao": sat,
            "best_alerts": alerts,
            "best_triggered_pairs": triggered_pairs,
            "best_has_quelante": bool(has_quelante),
            "risk_level": risk,
            "risk_reasons": list(risk_reasons),
        }

    def _risk_from_metrics(
        self,
        *,
        carga_sais_pct_mv: float,
        indice_saturacao: Optional[float],
        triggered_pairs: Sequence[Tuple[str, str]],
        totals: Dict[str, float],
        has_quelante: bool,
    ) -> Tuple[str, List[str]]:
        reasons: List[str] = []

        sat = float(indice_saturacao) if indice_saturacao is not None else None
        sal = float(carga_sais_pct_mv or 0.0)
        ca = float(totals.get("Ca", 0.0) or 0.0)
        so4 = float(totals.get("SO4", 0.0) or 0.0)

        if triggered_pairs:
            reasons.append(f"Pares críticos: {list(triggered_pairs)}")
        if sat is not None and sat >= 1.0:
            reasons.append(f"Índice de saturação >= 1.0 ({sat:.3f})")
        if sal >= 40.0:
            reasons.append(f"Carga salina alta ({sal:.1f}% m/v)")

        hard = bool(triggered_pairs) or (sat is not None and sat >= 1.0) or (sal >= 40.0)
        if hard:
            return "vermelho", reasons

        if sat is not None and sat >= 0.85:
            reasons.append(f"Índice de saturação alto ({sat:.3f})")
        if sal >= 30.0:
            reasons.append(f"Carga salina elevada ({sal:.1f}% m/v)")
        if ca > 0 and so4 > 0 and (not has_quelante):
            reasons.append("Ca + SO4 presentes sem quelante detectado")

        if reasons:
            return "amarelo", reasons
        return "verde", []

    def last_has_alerts(self) -> bool:
        if not self._records:
            return False
        s = self._records[0].summary or {}
        if (s.get("best_alerts") or []) or (s.get("best_triggered_pairs") or []):
            return True
        return str(s.get("risk_level") or "").strip().lower() in {"amarelo", "vermelho"}

    def _update_risk_bar(self, summary: Dict[str, Any]) -> None:
        level = str(summary.get("risk_level") or "").strip().lower()
        reasons = summary.get("risk_reasons") or []

        if level == "vermelho":
            color = ft.Colors.RED_400
            title = "Risco: ALTO"
        elif level == "amarelo":
            color = ft.Colors.AMBER_400
            title = "Risco: ATENÇÃO"
        elif level == "verde":
            color = ft.Colors.GREEN_400
            title = "Risco: OK"
        else:
            color = ft.Colors.BLUE_400
            title = "Risco: N/D"

        dots = ft.Row(
            [
                ft.Container(width=14, height=14, border_radius=7, bgcolor=(ft.Colors.GREEN_400 if level == "verde" else ft.Colors.with_opacity(0.15, ft.Colors.WHITE))),
                ft.Container(width=14, height=14, border_radius=7, bgcolor=(ft.Colors.AMBER_400 if level == "amarelo" else ft.Colors.with_opacity(0.15, ft.Colors.WHITE))),
                ft.Container(width=14, height=14, border_radius=7, bgcolor=(ft.Colors.RED_400 if level == "vermelho" else ft.Colors.with_opacity(0.15, ft.Colors.WHITE))),
            ],
            spacing=6,
        )

        reason_text = " | ".join([str(r) for r in reasons[:3]]) if reasons else "Sem alertas automáticos."
        self._risk_bar.content = ft.Row(
            [
                dots,
                ft.VerticalDivider(width=10, color=ft.Colors.TRANSPARENT),
                ft.Column(
                    [
                        ft.Text(title, size=13, weight=ft.FontWeight.BOLD, color=color),
                        ft.Text(reason_text, size=12, color=ft.Colors.with_opacity(0.85, ft.Colors.WHITE)),
                    ],
                    spacing=2,
                    expand=True,
                ),
            ],
            alignment=ft.MainAxisAlignment.START,
        )
        self._risk_bar.border = ft.border.all(1, ft.Colors.with_opacity(0.5, color))
        self._risk_bar.bgcolor = ft.Colors.with_opacity(0.08, color)

    def _render_list(self) -> None:
        self._list.controls.clear()

        for rec in self._records:
            s = rec.summary
            title = f"{rec.received_at} | V={int(round(float(s.get('volume_l') or 0)))} L | T={float(s.get('temp_c') or 0):.1f}°C | F{s.get('best_idx')}"
            alerts = s.get("best_alerts") or []
            subtitle = f"Alertas: {len(alerts)} | Sal: {float(s.get('best_carga_sais_pct_mv') or 0):.1f}% (m/v)"

            def on_open_details(_e, rid=rec.id) -> None:
                self._render_details(rid)

            tile = ft.ListTile(
                title=ft.Text(title, size=12, weight=ft.FontWeight.BOLD),
                subtitle=ft.Text(subtitle, size=11),
                on_click=on_open_details,
            )
            self._list.controls.append(tile)

        if self._page:
            self._page.update()

    def _render_details(self, record_id: str) -> None:
        rec = next((r for r in self._records if r.id == record_id), None)
        if not rec:
            self._details.content = ft.Text("Registro não encontrado.", size=12)
            if self._page:
                self._page.update()
            return

        s = rec.summary
        totals: Dict[str, float] = s.get("best_totals") or {}
        alerts: List[str] = s.get("best_alerts") or []
        risk_level = str(s.get("risk_level") or "").strip().lower()
        risk_reasons: List[str] = s.get("risk_reasons") or []
        self._update_risk_bar(s)

        def tot(k: str) -> str:
            v = float(totals.get(k, 0.0) or 0.0)
            return f"{v:.3f}%" if v > 0 else "-"

        metrics = ft.Row(
            [
                ft.Container(content=ft.Text(f"Sal (m/v): {float(s.get('best_carga_sais_pct_mv') or 0):.1f}%", size=12), padding=8),
                ft.Container(content=ft.Text(f"N: {tot('N')}", size=12), padding=8),
                ft.Container(content=ft.Text(f"P2O5: {tot('P2O5')}", size=12), padding=8),
                ft.Container(content=ft.Text(f"Ca: {tot('Ca')}", size=12), padding=8),
                ft.Container(content=ft.Text(f"SO4: {tot('SO4')}", size=12), padding=8),
            ],
            wrap=True,
        )

        diag_cards: List[ft.Control] = []
        def add_card(title: str, body: str, color: str) -> None:
            diag_cards.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(title, size=12, weight=ft.FontWeight.BOLD, color=color),
                            ft.Text(body, size=12),
                        ],
                        spacing=4,
                    ),
                    padding=10,
                    border=ft.border.all(1, ft.Colors.with_opacity(0.35, color)),
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.06, color),
                )
            )

        if risk_level == "vermelho":
            add_card("Semáforo", "Risco iminente de precipitação / instabilidade.", ft.Colors.RED_400)
        elif risk_level == "amarelo":
            add_card("Semáforo", "Limite de estabilidade próximo. Requer atenção.", ft.Colors.AMBER_400)
        elif risk_level == "verde":
            add_card("Semáforo", "Sem alertas automáticos relevantes.", ft.Colors.GREEN_400)

        if risk_reasons:
            add_card("Diagnóstico", " | ".join([str(r) for r in risk_reasons]), ft.Colors.AMBER_400 if risk_level != "vermelho" else ft.Colors.RED_400)

        triggered_pairs = s.get("best_triggered_pairs") or []
        if triggered_pairs:
            add_card("Pares críticos", str(list(triggered_pairs)), ft.Colors.RED_400)

        sat = _safe_float(s.get("best_indice_saturacao"))
        if sat is not None:
            if sat >= 1.0:
                add_card("Saturação", f"Índice {sat:.3f} (>= 1.0)", ft.Colors.RED_400)
            elif sat >= 0.85:
                add_card("Saturação", f"Índice {sat:.3f} (>= 0.85)", ft.Colors.AMBER_400)

        sal = float(s.get("best_carga_sais_pct_mv") or 0.0)
        if sal >= 40.0:
            add_card("Carga salina", f"{sal:.1f}% (m/v) (>= 40%)", ft.Colors.RED_400)
        elif sal >= 30.0:
            add_card("Carga salina", f"{sal:.1f}% (m/v) (>= 30%)", ft.Colors.AMBER_400)

        alert_controls = [ft.Text("Alertas", size=13, weight=ft.FontWeight.BOLD)]
        if alerts:
            alert_controls.extend([ft.Text(f"- {a}", size=12) for a in alerts])
        else:
            alert_controls.append(ft.Text("Sem alertas automáticos.", size=12, italic=True))

        payload = rec.payload
        lab = payload.get("lab") or {}
        ph_tf = ft.TextField(label="pH (bancada)", width=160, dense=True, value="" if lab.get("ph") is None else str(lab.get("ph")))
        ec_tf = ft.TextField(label="Condutividade (mS/cm)", width=220, dense=True, value="" if lab.get("ec") is None else str(lab.get("ec")))
        turb_tf = ft.TextField(label="Turbidez (NTU)", width=180, dense=True, value="" if lab.get("turbidez") is None else str(lab.get("turbidez")))
        obs_tf = ft.TextField(label="Observações (bancada)", dense=True, multiline=True, min_lines=2, max_lines=4, value=str(lab.get("observacoes") or ""))

        def on_save_lab(_e) -> None:
            new_lab = {
                "ph": _safe_float(ph_tf.value),
                "ec": _safe_float(ec_tf.value),
                "turbidez": _safe_float(turb_tf.value),
                "observacoes": str(obs_tf.value or ""),
            }
            rec.payload["lab"] = dict(new_lab)
            if self._page:
                self._page.snack_bar = ft.SnackBar(ft.Text("Dados de bancada salvos neste registro."))
                self._page.snack_bar.open = True
                self._page.update()

        outputs = payload.get("outputs") or []
        best = outputs[0] if outputs else {}
        lines = best.get("lines") or []
        line_controls = [ft.Text("BOM (melhor fórmula)", size=13, weight=ft.FontWeight.BOLD)]
        for l in lines[:60]:
            nm = str(l.get("insumo_nome") or "")
            mk = _safe_float(l.get("massa_kg")) or 0.0
            line_controls.append(ft.Text(f"- {nm}: {mk:.3f} kg", size=12))

        self._details.content = ft.Column(
            [
                ft.Text(f"Recebido em: {rec.received_at} | id={rec.id}", size=12),
                metrics,
                ft.Divider(),
                ft.Text("Indicadores de Risco", size=13, weight=ft.FontWeight.BOLD),
                ft.Row(diag_cards, wrap=True, spacing=10),
                ft.Divider(),
                ft.Text("Entrada de Dados de Bancada", size=13, weight=ft.FontWeight.BOLD),
                ft.Row([ph_tf, ec_tf, turb_tf], wrap=True, spacing=10),
                obs_tf,
                ft.Row([ft.ElevatedButton("SALVAR DADOS DE BANCADA", icon=ft.Icons.SAVE, on_click=on_save_lab)], wrap=True),
                ft.Divider(),
                ft.Column(alert_controls, spacing=4),
                ft.Divider(),
                ft.Column(line_controls, spacing=3),
            ],
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        if self._page:
            self._page.update()
