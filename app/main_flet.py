from __future__ import annotations

import asyncio
import ipaddress
import os
import sys
import threading
from pathlib import Path
from queue import Empty, Queue
from typing import Any
from urllib.parse import urlparse

import flet as ft

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from osint_engine.engine import InvestigationEngine
from osint_engine.exporters import export_all
from osint_engine.models import Finding, Investigation, InvestigationSeed
from osint_engine.normalization import normalize_seed, validate_seed

APP_VERSION = "0.2.0"
GREEN, DARK, PALE = "#1F4D3A", "#163A2C", "#E8F0EC"
GOLD, CREAM, MUTED, BORDER = "#B08D57", "#F7F4EE", "#5F666C", "#E1E5E2"


def first_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        return next((x.strip() for x in value if isinstance(x, str) and x.strip()), "")
    return ""


def safe_image(value: Any) -> str:
    url = first_text(value)
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").casefold()
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not host or host == "localhost" or host.endswith((".local", ".localhost")):
        return ""
    try:
        return url if ipaddress.ip_address(host).is_global else ""
    except ValueError:
        return url


def main(page: ft.Page) -> None:
    page.title = "OSINT Engine Institucional"
    page.window.width, page.window.height = 1180, 720
    page.window.min_width, page.window.min_height = 960, 620
    page.window.resizable = page.window.maximizable = True
    page.window.maximized = False
    page.padding = 0
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = "#FAFAF8"

    engine = InvestigationEngine(maigret_top_sites=int(os.getenv("OSINT_MAIGRET_TOP", "500")))
    events: Queue[tuple[str, Any]] = Queue()
    cancel_event = threading.Event()
    state = {"ready": False, "running": False, "result": None, "sites": 0}

    mode = ft.SegmentedButton(
        selected=["username"],
        segments=[
            ft.Segment(value="username", label=ft.Text("Usuario"), icon=ft.Icon(ft.Icons.ALTERNATE_EMAIL)),
            ft.Segment(value="name", label=ft.Text("Nombre"), icon=ft.Icon(ft.Icons.PERSON)),
            ft.Segment(value="phone", label=ft.Text("Teléfono"), icon=ft.Icon(ft.Icons.PHONE)),
        ],
    )
    target = ft.TextField(label="Usuario / alias o correo", hint_text="jose.gomez o jose.gomez@dominio.com", prefix_icon=ft.Icons.ALTERNATE_EMAIL)
    case_id = ft.TextField(label="Folio / caso (opcional)", prefix_icon=ft.Icons.FOLDER_OPEN)
    help_text = ft.Text("Si pega un correo, Maigret recibe sólo el texto anterior a @.", size=10, color=MUTED)
    status = ft.Text("Inicializando...", size=10, color=MUTED)
    progress_label = ft.Text("", size=9, color=MUTED)
    progress = ft.ProgressBar(value=0, visible=False, color=GREEN)
    run = ft.FilledButton(content="Investigar", icon=ft.Icons.SEARCH, bgcolor=GREEN, color=ft.Colors.WHITE, disabled=True)
    stop = ft.OutlinedButton(content="Detener", icon=ft.Icons.STOP_CIRCLE, visible=False)
    export = ft.FilledButton(content="Exportar expediente", icon=ft.Icons.DOWNLOAD, bgcolor=GOLD, color=ft.Colors.WHITE, disabled=True)

    summary = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO)
    results = ft.ListView(spacing=8, expand=True)
    evidence = ft.ListView(spacing=8, expand=True)
    audit = ft.ListView(spacing=4, expand=True)
    tabs = ft.Tabs(
        length=4,
        selected_index=0,
        expand=True,
        content=ft.Column(
            [
                ft.TabBar(tabs=[
                    ft.Tab(label="Resumen", icon=ft.Icons.DASHBOARD),
                    ft.Tab(label="Resultados Maigret", icon=ft.Icons.TRAVEL_EXPLORE),
                    ft.Tab(label="Evidencia", icon=ft.Icons.FACT_CHECK),
                    ft.Tab(label="Auditoría", icon=ft.Icons.RECEIPT_LONG),
                ]),
                ft.TabBarView(expand=True, controls=[
                    ft.Container(summary, padding=14), ft.Container(results, padding=14),
                    ft.Container(evidence, padding=14), ft.Container(audit, padding=14),
                ]),
            ], expand=True,
        ),
    )

    loader_title = ft.Text("Inicializando OSINT Engine", size=22, weight=ft.FontWeight.BOLD, color=DARK)
    loader_status = ft.Text("Preparando Maigret y su base de sitios...", size=11, color=MUTED, text_align=ft.TextAlign.CENTER)
    retry = ft.FilledButton(content="Reintentar", icon=ft.Icons.REFRESH, visible=False, bgcolor=GREEN, color=ft.Colors.WHITE)
    loader = ft.Container(
        expand=True, bgcolor=CREAM, alignment=ft.Alignment.CENTER,
        content=ft.Container(
            width=460, padding=30, bgcolor=ft.Colors.WHITE, border=ft.Border.all(1, BORDER), border_radius=16,
            content=ft.Column([
                ft.Icon(ft.Icons.TRAVEL_EXPLORE, size=42, color=GREEN), loader_title, loader_status,
                ft.ProgressRing(width=32, height=32, color=GOLD), retry,
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=14, tight=True),
        ),
    )

    def current_mode() -> str:
        return (mode.selected or ["username"])[0]

    def on_mode(_e=None) -> None:
        selected = current_mode()
        target.value = ""
        export.disabled, state["result"] = True, None
        if selected == "username":
            target.label, target.hint_text, target.prefix_icon = "Usuario / alias o correo", "jose.gomez o jose.gomez@dominio.com", ft.Icons.ALTERNATE_EMAIL
            help_text.value = "Si pega un correo, Maigret recibe sólo el texto anterior a @."
        elif selected == "name":
            target.label, target.hint_text, target.prefix_icon = "Nombre completo", "Nombre y apellidos", ft.Icons.PERSON
            help_text.value = "Modo separado: no genera usernames ni envía nombres a Maigret."
        else:
            target.label, target.hint_text, target.prefix_icon = "Número de teléfono", "+52 55 1234 5678", ft.Icons.PHONE
            help_text.value = "Modo separado: Maigret no se usa para números telefónicos."
        page.update()

    def make_seed() -> InvestigationSeed:
        value, selected = target.value or "", current_mode()
        return normalize_seed(InvestigationSeed(
            username=value if selected == "username" else "",
            person_name=value if selected == "name" else "",
            phone=value if selected == "phone" else "",
            case_id=case_id.value or "",
        ))

    def log(text: str) -> None:
        audit.controls.append(ft.Text(text, size=9, color=MUTED, selectable=True))

    def worker(seed: InvestigationSeed) -> None:
        try:
            events.put(("done", engine.run(seed, cancel_event, lambda *args: events.put(("progress", args)))))
        except Exception as exc:
            events.put(("error", str(exc)))

    async def poll() -> None:
        while state["running"]:
            try:
                while True:
                    kind, payload = events.get_nowait()
                    if kind == "progress":
                        _, checked, total, detail = payload
                        progress.visible = total > 0
                        progress.value = checked / total if total else 0
                        progress_label.value = f"{checked}/{total} · {detail}" if total else detail
                    elif kind == "done":
                        finish(payload)
                        return
                    else:
                        fail(payload)
                        return
            except Empty:
                pass
            page.update()
            await asyncio.sleep(0.12)

    def on_run(_e) -> None:
        seed = make_seed()
        errors = validate_seed(seed)
        if errors:
            page.show_dialog(ft.SnackBar(ft.Text(" ".join(errors))))
            return
        cancel_event.clear(); state["running"] = True; state["result"] = None
        run.disabled = export.disabled = True
        stop.visible = bool(seed.username)
        progress.visible = bool(seed.username); progress.value = 0
        status.value = "Consultando Maigret..." if seed.username else "Registrando objetivo independiente..."
        summary.controls.clear(); results.controls.clear(); evidence.controls.clear(); audit.controls.clear()
        log(f"Inicio · modo={current_mode()} · objetivo normalizado={seed.username or seed.person_name or seed.phone}")
        threading.Thread(target=worker, args=(seed,), daemon=True).start()
        page.run_task(poll); page.update()

    def on_stop(_e) -> None:
        cancel_event.set(); stop.disabled = True; status.value = "Detención solicitada; se conservarán resultados parciales."; page.update()

    def finish(inv: Investigation) -> None:
        state["running"], state["result"] = False, inv
        run.disabled, export.disabled, stop.visible, stop.disabled, progress.visible = False, False, False, False, False
        status.value = "Investigación concluida" if inv.status != "cancelled" else "Investigación detenida"
        render(inv); log(f"Fin · estado={inv.status} · hallazgos={len(inv.findings)}"); page.update()

    def fail(message: str) -> None:
        state["running"] = False; run.disabled = False; stop.visible = progress.visible = False
        status.value = "Error de ejecución"; log(f"Error · {message}"); page.show_dialog(ft.SnackBar(ft.Text(message))); page.update()

    def on_export(_e) -> None:
        inv = state.get("result")
        if not inv:
            return
        try:
            paths = export_all(inv)
        except Exception as exc:
            page.show_dialog(ft.SnackBar(ft.Text(f"No fue posible exportar: {exc}"))); return
        native = any(p.name.startswith("maigret_") and p.suffix == ".html" for p in paths)
        page.show_dialog(ft.SnackBar(ft.Text(f"{len(paths)} archivos en {paths[0].parent}." + (" Incluye reporte HTML nativo de Maigret." if native else ""))))
        log("Exportados · " + ", ".join(p.name for p in paths)); page.update()

    def metric(title: str, value: str) -> ft.Container:
        return ft.Container(col={"xs": 6, "md": 3}, padding=12, bgcolor=ft.Colors.WHITE, border=ft.Border.all(1, BORDER), border_radius=9,
            content=ft.Column([ft.Text(title, size=9, color=MUTED), ft.Text(value, size=17, weight=ft.FontWeight.BOLD, color=DARK)], spacing=2))

    def render(inv: Investigation) -> None:
        profiles = [f for f in inv.findings if f.entity_type == "social_account"]
        with_images = sum(bool(profile_image(f)) for f in profiles)
        obj = inv.seed.username or inv.seed.person_name or inv.seed.phone
        label = "Usuario" if inv.seed.username else "Nombre" if inv.seed.person_name else "Teléfono"
        summary.controls[:] = [
            ft.ResponsiveRow([metric("Modo", label), metric("Perfiles", str(len(profiles))), metric("Con imagen", str(with_images)), metric("Estado", inv.status.replace("_", " ").title())]),
            ft.Container(padding=14, bgcolor=PALE if inv.seed.username else "#F4EEE5", border_radius=9,
                content=ft.Column([ft.Text("Objetivo", weight=ft.FontWeight.BOLD), ft.Text(obj, selectable=True),
                    ft.Text((f"Maigret consultó hasta {state['sites']} sitios priorizados. Una coincidencia de alias no demuestra identidad." if inv.seed.username else "Este objetivo quedó separado de Maigret; no se generaron aliases ni consultas indirectas."), size=10, color=MUTED)], spacing=4)),
        ]
        if inv.notes:
            summary.controls.append(ft.Text("Advertencias: " + " · ".join(inv.notes), size=10, color="#8A5A00"))
        results.controls.clear()
        for finding in sorted(profiles, key=lambda x: x.platform.casefold()):
            results.controls.append(result_card(finding))
        if not profiles:
            results.controls.append(ft.Container(padding=25, alignment=ft.Alignment.CENTER,
                content=ft.Text("Maigret no encontró perfiles confirmados para este alias." if inv.seed.username else "Este modo no ejecuta Maigret en la versión actual.", color=MUTED)))
        evidence.controls.clear()
        for finding in inv.findings:
            if finding.evidence:
                evidence.controls.append(evidence_card(finding))

    def profile_image(finding: Finding) -> str:
        ids = finding.evidence.get("ids_data") or {}
        return safe_image(finding.evidence.get("profile_image_url") or ids.get("image"))

    def result_card(finding: Finding) -> ft.Container:
        ids = finding.evidence.get("ids_data") or {}
        image, fullname, location = profile_image(finding), first_text(ids.get("fullname") or ids.get("name")), first_text(ids.get("location"))
        avatar = ft.Container(width=64, height=64, border_radius=10, bgcolor=PALE, alignment=ft.Alignment.CENTER,
            content=ft.Image(src=image, width=64, height=64, error_content=ft.Icon(ft.Icons.ACCOUNT_CIRCLE, size=44, color=GREEN)) if image else ft.Icon(ft.Icons.ACCOUNT_CIRCLE, size=44, color=GREEN))
        text = [ft.Text(finding.platform, weight=ft.FontWeight.BOLD, size=13), ft.Text(finding.source_url, size=9, selectable=True, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)]
        if fullname: text.append(ft.Text(fullname, size=10, color=DARK))
        if location: text.append(ft.Text(location, size=9, color=MUTED))
        return ft.Container(padding=11, bgcolor=ft.Colors.WHITE, border=ft.Border.all(1, BORDER), border_radius=10,
            content=ft.Row([avatar, ft.Column(text, spacing=2, expand=True), ft.FilledButton(content="Abrir perfil", icon=ft.Icons.OPEN_IN_NEW, url=finding.source_url, bgcolor=GREEN, color=ft.Colors.WHITE)]))

    def evidence_card(finding: Finding) -> ft.Container:
        lines = []
        for key, value in finding.evidence.items():
            rendered = str(value)
            if len(rendered) > 380: rendered = rendered[:377] + "..."
            lines.append(ft.Text(f"{key}: {rendered}", size=9, selectable=True))
        return ft.Container(padding=11, bgcolor=ft.Colors.WHITE, border=ft.Border.all(1, BORDER), border_radius=9,
            content=ft.Column([ft.Text(f"{finding.source_engine} · {finding.platform or finding.entity_type}", weight=ft.FontWeight.BOLD, size=11), *lines], spacing=3))

    async def initialize() -> None:
        state["ready"] = False; run.disabled = True; retry.visible = False; loader.visible = True
        loader_title.value, loader_status.value = "Inicializando OSINT Engine", "Preparando Maigret y su base de sitios..."; page.update()
        try:
            info = await asyncio.to_thread(engine.prepare)
        except Exception as exc:
            loader_title.value, loader_status.value, retry.visible = "No fue posible iniciar Maigret", str(exc), True; page.update(); return
        state["sites"], state["ready"] = int(info.get("maigret_sites") or 0), True
        run.disabled = False; status.value = f"Listo · Maigret preparado con {state['sites']} sitios"; loader.visible = False; page.update()

    mode.on_change = on_mode; run.on_click = on_run; stop.on_click = on_stop; export.on_click = on_export; retry.on_click = lambda _e: page.run_task(initialize)

    header = ft.Container(padding=ft.Padding.symmetric(horizontal=20, vertical=13), bgcolor=DARK,
        content=ft.Row([ft.Icon(ft.Icons.TRAVEL_EXPLORE, color=GOLD, size=30),
            ft.Column([ft.Text("OSINT Engine Institucional", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE), ft.Text("Investigación pública · Maigret como motor principal", size=10, color="#DCE7E2")], spacing=1),
            ft.Container(expand=True), ft.Text(f"v{APP_VERSION}", size=10, color="#DCE7E2")]))
    sidebar = ft.Container(width=350, padding=16, bgcolor=ft.Colors.WHITE, border=ft.Border.only(right=ft.BorderSide(1, BORDER)),
        content=ft.Column([ft.Text("Nueva investigación", size=16, weight=ft.FontWeight.BOLD, color=DARK), ft.Text("Usuario, nombre o teléfono; cada modo conserva su propia lógica.", size=10, color=MUTED), mode, target, help_text, case_id, ft.Divider(),
            ft.Container(padding=11, bgcolor=CREAM, border_radius=9, content=ft.Column([ft.Text("✓  Maigret 0.6.5", weight=ft.FontWeight.BOLD, size=11), ft.Text("Usuario · hasta 500 sitios · reporte HTML nativo", size=9, color=MUTED)], spacing=2)),
            ft.Row([run, stop], wrap=True), export, progress, progress_label, status], spacing=9, scroll=ft.ScrollMode.AUTO))
    shell = ft.Column([header, ft.Row([sidebar, ft.Container(tabs, expand=True, padding=8)], expand=True, spacing=0, vertical_alignment=ft.CrossAxisAlignment.STRETCH)], expand=True, spacing=0)
    page.add(ft.Stack([shell, loader], expand=True))
    page.run_task(initialize)


if __name__ == "__main__":
    ft.run(main)
