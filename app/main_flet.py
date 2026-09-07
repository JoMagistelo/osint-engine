from __future__ import annotations

import asyncio
import math
import os
import sys
import threading
from pathlib import Path
from queue import Empty, Queue
from typing import Any

import flet as ft
import flet.canvas as cv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from osint_engine.correlation import confidence_label, seed_node_label
from osint_engine.engine import InvestigationEngine
from osint_engine.exporters import export_all
from osint_engine.models import Investigation, InvestigationSeed
from osint_engine.normalization import normalize_seed, validate_seed
from osint_engine.security import safe_seed_summary

APP_VERSION = "0.1.1"
GOB_GREEN = "#1F4D3A"
GOB_GREEN_DARK = "#163A2C"
GOB_GREEN_LIGHT = "#E8F0EC"
GOB_GOLD = "#B08D57"
GOB_GOLD_LIGHT = "#F4EEE5"
GOB_CREAM = "#F7F4EE"
DANGER = "#A63D40"
TEXT_MUTED = "#5F666C"


def main(page: ft.Page) -> None:
    page.title = "OSINT Engine Institucional"
    page.window.width = 1240
    page.window.height = 760
    page.window.min_width = 980
    page.window.min_height = 650
    page.window.maximized = True
    page.padding = 14
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = "#FAFAF8"

    events: Queue[tuple[str, Any]] = Queue()
    cancel_event = threading.Event()
    engine = InvestigationEngine(maigret_top_sites=int(os.getenv("OSINT_MAIGRET_TOP", "250")))
    state: dict[str, Any] = {"running": False, "investigation": None}

    case_id = ft.TextField(label="Folio / caso (opcional)", height=46, text_size=12)
    person_name = ft.TextField(label="Nombre", height=46, text_size=12, prefix_icon=ft.Icons.PERSON)
    username = ft.TextField(label="Usuario / alias", height=46, text_size=12, prefix_icon=ft.Icons.ALTERNATE_EMAIL)
    email = ft.TextField(label="Correo", height=46, text_size=12, prefix_icon=ft.Icons.EMAIL)
    phone = ft.TextField(label="Teléfono", height=46, text_size=12, prefix_icon=ft.Icons.PHONE)
    derive_aliases = ft.Checkbox(
        label="Probar como hipótesis el alias derivado del correo",
        value=False,
        tooltip="El texto antes de @ se marca como hipótesis de baja confianza; no prueba identidad.",
    )

    status_text = ft.Text("Listo", size=11, color=TEXT_MUTED)
    progress_text = ft.Text("", size=11, color=TEXT_MUTED)
    progress_bar = ft.ProgressBar(value=0, visible=False, color=GOB_GREEN)
    run_button = ft.FilledButton(
        content="Iniciar análisis",
        icon=ft.Icons.SEARCH,
        bgcolor=GOB_GREEN,
        color=ft.Colors.WHITE,
    )
    stop_button = ft.OutlinedButton(
        content="Detener",
        icon=ft.Icons.STOP_CIRCLE,
        visible=False,
        icon_color=DANGER,
        style=ft.ButtonStyle(color=DANGER),
    )
    export_button = ft.FilledButton(
        content="Exportar evidencia",
        icon=ft.Icons.DOWNLOAD,
        bgcolor=GOB_GOLD,
        color=ft.Colors.WHITE,
        disabled=True,
    )

    summary_view = ft.Column(spacing=10)
    findings_view = ft.ListView(spacing=6, expand=True)
    graph_host = ft.Container(expand=True, bgcolor=ft.Colors.WHITE, border_radius=10)
    evidence_view = ft.ListView(spacing=6, expand=True)
    log_view = ft.ListView(spacing=4, expand=True)

    tabs = ft.Tabs(
        length=5,
        selected_index=0,
        animation_duration=220,
        expand=True,
        content=ft.Column(
            expand=True,
            controls=[
                ft.TabBar(
                    tabs=[
                        ft.Tab(label="Resumen", icon=ft.Icons.DASHBOARD),
                        ft.Tab(label="Hallazgos", icon=ft.Icons.TRAVEL_EXPLORE),
                        ft.Tab(label="Red de vínculos", icon=ft.Icons.HUB),
                        ft.Tab(label="Evidencias", icon=ft.Icons.FACT_CHECK),
                        ft.Tab(label="Auditoría", icon=ft.Icons.RECEIPT_LONG),
                    ]
                ),
                ft.TabBarView(
                    expand=True,
                    controls=[
                        ft.Container(content=summary_view, padding=10, expand=True),
                        ft.Container(content=findings_view, padding=10, expand=True),
                        ft.Container(content=graph_host, padding=10, expand=True),
                        ft.Container(content=evidence_view, padding=10, expand=True),
                        ft.Container(content=log_view, padding=10, expand=True),
                    ],
                ),
            ],
        ),
    )

    def log(message: str) -> None:
        log_view.controls.append(ft.Text(message, size=10, color=TEXT_MUTED))
        page.update()

    def make_seed() -> InvestigationSeed:
        return normalize_seed(
            InvestigationSeed(
                person_name=person_name.value or "",
                username=username.value or "",
                email=email.value or "",
                phone=phone.value or "",
                case_id=case_id.value or "",
                derive_aliases=bool(derive_aliases.value),
            )
        )

    def progress(engine_key: str, checked: int, total: int, detail: str) -> None:
        events.put(("progress", (engine_key, checked, total, detail)))

    def worker(seed: InvestigationSeed) -> None:
        try:
            result = engine.run(seed, cancel_event, progress)
            events.put(("done", result))
        except Exception as exc:
            events.put(("error", str(exc)))

    async def poll_events() -> None:
        while state["running"]:
            handled = False
            try:
                while True:
                    kind, payload = events.get_nowait()
                    handled = True
                    if kind == "progress":
                        engine_key, checked, total, detail = payload
                        progress_bar.visible = total > 0
                        progress_bar.value = (checked / total) if total else 0
                        progress_text.value = f"{engine_key}: {checked}/{total} · {detail}"
                    elif kind == "done":
                        finish(payload)
                        return
                    elif kind == "error":
                        fail(payload)
                        return
            except Empty:
                pass
            if handled:
                page.update()
            await asyncio.sleep(0.12)

    def on_run(_e: ft.ControlEvent) -> None:
        seed = make_seed()
        errors = validate_seed(seed)
        if errors:
            page.show_dialog(ft.SnackBar(ft.Text(" ".join(errors))))
            return
        cancel_event.clear()
        state["running"] = True
        state["investigation"] = None
        run_button.disabled = True
        stop_button.visible = True
        stop_button.disabled = False
        export_button.disabled = True
        progress_bar.visible = True
        progress_bar.value = 0
        progress_text.value = "Preparando motores..."
        status_text.value = "Analizando fuentes públicas"
        summary_view.controls.clear()
        findings_view.controls.clear()
        evidence_view.controls.clear()
        graph_host.content = ft.Container(
            content=ft.ProgressRing(),
            alignment=ft.Alignment.CENTER,
            expand=True,
        )
        log_view.controls.clear()
        log(f"Inicio de investigación: {safe_seed_summary(seed.person_name, seed.username, seed.email, seed.phone)}")
        threading.Thread(target=worker, args=(seed,), daemon=True).start()
        page.run_task(poll_events)
        page.update()

    def on_stop(_e: ft.ControlEvent) -> None:
        if not state["running"]:
            return
        cancel_event.set()
        stop_button.disabled = True
        status_text.value = "Detención solicitada; se conservarán los hallazgos ya obtenidos."
        log("Detención solicitada por el operador.")
        page.update()

    def finish(investigation: Investigation) -> None:
        state["running"] = False
        state["investigation"] = investigation
        run_button.disabled = False
        stop_button.visible = False
        progress_bar.visible = False
        progress_text.value = ""
        export_button.disabled = False
        status_text.value = (
            "Análisis detenido con resultados parciales"
            if investigation.status == "cancelled"
            else "Análisis concluido"
        )
        render_investigation(investigation)
        log(
            f"Fin: estado={investigation.status}; hallazgos={len(investigation.findings)}; "
            f"advertencias={len(investigation.notes)}"
        )
        page.update()

    def fail(message: str) -> None:
        state["running"] = False
        run_button.disabled = False
        stop_button.visible = False
        progress_bar.visible = False
        status_text.value = "Error de ejecución"
        page.show_dialog(ft.SnackBar(ft.Text(message)))
        log(f"Error de motor: {message}")
        page.update()

    def on_export(_e: ft.ControlEvent) -> None:
        investigation: Investigation | None = state.get("investigation")
        if not investigation:
            return
        try:
            paths = export_all(investigation)
        except Exception as exc:
            page.show_dialog(ft.SnackBar(ft.Text(f"No fue posible exportar: {exc}")))
            return
        folder = paths[0].parent
        page.show_dialog(ft.SnackBar(ft.Text(f"Exportados JSON, CSV y GraphML en: {folder}")))
        log(f"Exportación generada en {folder}")

    def render_investigation(investigation: Investigation) -> None:
        account_findings = [f for f in investigation.findings if f.entity_type == "social_account"]
        provided = [f for f in investigation.findings if f.status == "provided"]
        candidates = [f for f in investigation.findings if f.status in {"hypothesis", "candidate_profile"}]
        summary_view.controls[:] = [
            ft.ResponsiveRow(
                controls=[
                    metric("Identificadores", str(len(provided))),
                    metric("Perfiles encontrados", str(len(account_findings))),
                    metric("Hipótesis", str(len(candidates))),
                    metric("Estado", investigation.status.replace("_", " ").title()),
                ],
            ),
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Criterio de interpretación", weight=ft.FontWeight.BOLD, size=13),
                        ft.Text(
                            "Una coincidencia de usuario confirma que ese alias existe en el sitio consultado; "
                            "no demuestra por sí sola que todas las cuentas pertenezcan a la misma persona.",
                            size=11,
                            color=TEXT_MUTED,
                        ),
                    ],
                    spacing=4,
                ),
                padding=12,
                bgcolor=GOB_GOLD_LIGHT,
                border_radius=8,
            ),
        ]
        if investigation.notes:
            summary_view.controls.append(
                ft.Container(
                    content=ft.Column([ft.Text("Advertencias", weight=ft.FontWeight.BOLD)] + [ft.Text(n, size=10) for n in investigation.notes]),
                    padding=12,
                    bgcolor="#FFF7E6",
                    border_radius=8,
                )
            )

        findings_view.controls.clear()
        evidence_view.controls.clear()
        for finding in sorted(investigation.findings, key=lambda f: (-f.confidence, f.platform, f.value)):
            findings_view.controls.append(finding_card(finding))
            if finding.evidence:
                evidence_view.controls.append(evidence_card(finding))
        if not findings_view.controls:
            findings_view.controls.append(ft.Text("Sin hallazgos.", color=TEXT_MUTED))
        graph_host.content = build_graph(investigation)

    def metric(title: str, value: str) -> ft.Container:
        return ft.Container(
            col={"xs": 6, "md": 3},
            padding=12,
            bgcolor=ft.Colors.WHITE,
            border=ft.Border.all(1, "#E1E5E2"),
            border_radius=9,
            content=ft.Column(
                [
                    ft.Text(title, size=9, color=TEXT_MUTED),
                    ft.Text(value, size=18, weight=ft.FontWeight.BOLD, color=GOB_GREEN_DARK),
                ],
                spacing=3,
            ),
        )

    def finding_card(finding) -> ft.Container:
        url_button = (
            ft.TextButton(content="Abrir fuente", icon=ft.Icons.OPEN_IN_NEW, url=finding.source_url)
            if finding.source_url
            else ft.Container()
        )
        return ft.Container(
            padding=10,
            bgcolor=ft.Colors.WHITE,
            border=ft.Border.all(1, "#E5E8E6"),
            border_radius=8,
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.ACCOUNT_CIRCLE if finding.platform else ft.Icons.KEY, color=GOB_GREEN),
                    ft.Column(
                        [
                            ft.Text(finding.platform or finding.entity_type, weight=ft.FontWeight.BOLD, size=12),
                            ft.Text(finding.value, size=10, selectable=True, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(
                                f"{finding.status} · confianza {confidence_label(finding.confidence)} ({finding.confidence:.0%})",
                                size=9,
                                color=TEXT_MUTED,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    url_button,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def evidence_card(finding) -> ft.Container:
        evidence_lines = []
        for key, value in finding.evidence.items():
            rendered = str(value)
            if len(rendered) > 260:
                rendered = rendered[:257] + "..."
            evidence_lines.append(ft.Text(f"{key}: {rendered}", size=9, selectable=True))
        return ft.Container(
            padding=10,
            bgcolor=ft.Colors.WHITE,
            border=ft.Border.all(1, "#E5E8E6"),
            border_radius=8,
            content=ft.Column(
                [
                    ft.Text(f"{finding.source_engine} · {finding.platform or finding.entity_type}", weight=ft.FontWeight.BOLD, size=11),
                    *evidence_lines,
                ],
                spacing=3,
            ),
        )

    def build_graph(investigation: Investigation) -> ft.Control:
        accounts = [f for f in investigation.findings if f.entity_type == "social_account"][:40]
        identifiers = [f for f in investigation.findings if f.status == "provided"][:8]
        width, height = 1040, 600
        cx, cy = width / 2, height / 2
        shapes: list[cv.Shape] = []
        line_paint = ft.Paint(color="#C9D2CD", stroke_width=1.5)
        root_paint = ft.Paint(color=GOB_GREEN, style=ft.PaintingStyle.FILL)
        id_paint = ft.Paint(color=GOB_GOLD, style=ft.PaintingStyle.FILL)
        account_paint = ft.Paint(color="#56776A", style=ft.PaintingStyle.FILL)

        def add_node(x: float, y: float, label: str, paint: ft.Paint, radius: float) -> None:
            shapes.append(cv.Circle(x=x, y=y, radius=radius, paint=paint))
            shapes.append(
                cv.Text(
                    x=x,
                    y=y + radius + 5,
                    value=label[:25],
                    max_width=150,
                    max_lines=2,
                    alignment=ft.Alignment.TOP_CENTER,
                    text_align=ft.TextAlign.CENTER,
                    style=ft.TextStyle(size=10, weight=ft.FontWeight.W_600, color=GOB_GREEN_DARK),
                )
            )

        add_node(cx, cy, seed_node_label(investigation.seed), root_paint, 24)
        id_positions: dict[str, tuple[float, float]] = {}
        count_ids = max(len(identifiers), 1)
        for i, finding in enumerate(identifiers):
            angle = (2 * math.pi * i / count_ids) - math.pi / 2
            x, y = cx + 170 * math.cos(angle), cy + 150 * math.sin(angle)
            shapes.append(cv.Line(x1=cx, y1=cy, x2=x, y2=y, paint=line_paint))
            add_node(x, y, finding.entity_type.replace("person_", ""), id_paint, 14)
            id_positions[finding.value] = (x, y)

        count_accounts = max(len(accounts), 1)
        for i, finding in enumerate(accounts):
            angle = (2 * math.pi * i / count_accounts) - math.pi / 2
            x, y = cx + 390 * math.cos(angle), cy + 250 * math.sin(angle)
            parent = id_positions.get(finding.parent_value, (cx, cy))
            shapes.append(cv.Line(x1=parent[0], y1=parent[1], x2=x, y2=y, paint=line_paint))
            add_node(x, y, finding.platform or "perfil", account_paint, 9)

        if not accounts:
            shapes.append(
                cv.Text(
                    x=cx,
                    y=cy + 70,
                    value="Aún no hay perfiles para representar.",
                    alignment=ft.Alignment.TOP_CENTER,
                    style=ft.TextStyle(size=12, color=TEXT_MUTED),
                )
            )
        canvas = cv.Canvas(width=width, height=height, shapes=shapes)
        return ft.InteractiveViewer(
            content=canvas,
            constrained=False,
            min_scale=0.55,
            max_scale=3.0,
            boundary_margin=ft.Margin.all(160),
        )

    run_button.on_click = on_run
    stop_button.on_click = on_stop
    export_button.on_click = on_export

    header = ft.Container(
        padding=ft.Padding.symmetric(horizontal=18, vertical=12),
        bgcolor=GOB_GREEN_DARK,
        border_radius=10,
        content=ft.Row(
            [
                ft.Icon(ft.Icons.HUB, color=GOB_GOLD, size=30),
                ft.Column(
                    [
                        ft.Text("OSINT Engine Institucional", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ft.Text("Análisis de fuentes públicas · evidencia trazable", size=10, color="#DCE7E2"),
                    ],
                    spacing=1,
                ),
                ft.Container(expand=True),
                ft.Text(f"v{APP_VERSION}", color="#DCE7E2", size=10),
            ]
        ),
    )

    left = ft.Container(
        width=330,
        padding=14,
        bgcolor=ft.Colors.WHITE,
        border=ft.Border.all(1, "#E1E5E2"),
        border_radius=10,
        content=ft.Column(
            [
                ft.Text("Nueva investigación", size=15, weight=ft.FontWeight.BOLD, color=GOB_GREEN_DARK),
                ft.Text("Capture uno o varios identificadores.", size=10, color=TEXT_MUTED),
                case_id,
                person_name,
                username,
                email,
                phone,
                derive_aliases,
                ft.Divider(height=8),
                ft.Text("Motores", size=11, weight=ft.FontWeight.BOLD),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.CHECK_CIRCLE, color=GOB_GREEN),
                    title=ft.Text("Maigret", size=11),
                    subtitle=ft.Text("Activo · usuario/alias", size=9),
                    dense=True,
                ),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.LOCK_CLOCK, color=TEXT_MUTED),
                    title=ft.Text("SpiderFoot", size=11),
                    subtitle=ft.Text("Adaptador preparado · no habilitado en v0.1", size=9),
                    dense=True,
                ),
                ft.Row([run_button, stop_button], wrap=True),
                export_button,
                progress_bar,
                progress_text,
                status_text,
            ],
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
        ),
    )

    page.add(
        header,
        ft.Row(
            [left, ft.Container(content=tabs, expand=True, height=page.window.height - 115)],
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
    )


if __name__ == "__main__":
    ft.run(main)
