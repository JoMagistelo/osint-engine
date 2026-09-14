from __future__ import annotations

import asyncio
import inspect
import logging
import uuid
from importlib.resources import files
from threading import Event, Lock
from typing import Any

from .base import AdapterInfo, ProgressCallback
from ..models import Finding, InvestigationSeed, json_safe
from ..normalization import UsernameCandidate, username_search_candidates


class _ProgressNotifier:
    """Implementa el contrato de notificación usado por Maigret 0.6.5."""

    def __init__(
        self,
        engine_key: str,
        total: int,
        callback: ProgressCallback | None,
        *,
        identifier: str,
        offset: int = 0,
        grand_total: int | None = None,
        cancel_event: Event | None = None,
    ) -> None:
        self.engine_key = engine_key
        self.total = max(total, 1)
        self.callback = callback
        self.identifier = identifier
        self.offset = max(offset, 0)
        self.grand_total = max(grand_total or self.total, 1)
        self.cancel_event = cancel_event
        self.checked = 0
        self.found = 0

    def _emit(self, detail: str) -> None:
        if self.callback:
            self.callback(
                self.engine_key,
                min(self.offset + self.checked, self.grand_total),
                self.grand_total,
                detail,
            )

    def start(self, message: str | None = None, id_type: str = "username") -> None:
        if message:
            self.identifier = str(message)
        self._emit(f"{self.identifier} · iniciando")

    def update(self, status: Any, similar_search: bool = False) -> None:
        self.checked = min(self.checked + 1, self.total)
        try:
            if status.is_found():
                self.found += 1
        except Exception:
            pass
        self._emit(f"{self.identifier} · {self.found} coincidencias")

    def finish(self, message: str | None = None) -> None:
        if not (self.cancel_event and self.cancel_event.is_set()):
            self.checked = self.total
        self._emit(f"{self.identifier} · {self.found} coincidencias")

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._emit(f"{self.identifier} · aviso: {message}")

    def enrich(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._emit(f"{self.identifier} · enriqueciendo perfil")

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._emit(f"{self.identifier} · {message}")

    def success(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._emit(f"{self.identifier} · {message}")


class MaigretAdapter:
    info = AdapterInfo(
        key="maigret",
        name="Maigret",
        enabled=True,
        description="Búsqueda pública de nombres de usuario en sitios soportados por Maigret.",
    )

    def __init__(self, top_sites: int = 500, timeout: int = 15) -> None:
        self.top_sites = max(int(top_sites), 1)
        self.timeout = max(int(timeout), 1)
        self._prepare_lock = Lock()
        self._sites: dict[str, Any] | None = None
        self._maigret_search: Any = None
        self._report_runs: list[tuple[str, str, dict[str, Any]]] = []

    def prepare(self) -> int:
        """Carga y conserva en memoria la base de sitios incluida con Maigret."""

        if self._sites is not None and self._maigret_search is not None:
            return len(self._sites)

        with self._prepare_lock:
            if self._sites is not None and self._maigret_search is not None:
                return len(self._sites)
            try:
                from maigret import search as maigret_search
                from maigret.sites import MaigretDatabase
            except Exception as exc:
                raise RuntimeError(
                    'Maigret 0.6.5 no está disponible. Reinstale con pip install -e ".[desktop]".'
                ) from exc

            data_path = files("maigret").joinpath("resources", "data.json")
            database = MaigretDatabase().load_from_path(str(data_path))
            self._sites = database.ranked_sites_dict(top=self.top_sites)
            self._maigret_search = maigret_search
            return len(self._sites)

    def report_runs(self) -> list[tuple[str, str, dict[str, Any]]]:
        """Devuelve las ejecuciones crudas requeridas por el reporte oficial."""

        return list(self._report_runs)

    def run(
        self,
        seed: InvestigationSeed,
        cancel_event: Event,
        progress: ProgressCallback | None = None,
    ) -> list[Finding]:
        candidates = username_search_candidates(seed)
        self._report_runs = []

        if not candidates:
            if progress:
                progress(self.info.key, 0, 0, "Este modo no requiere Maigret")
            return []

        self.prepare()
        return asyncio.run(self._run_all(candidates, cancel_event, progress))

    async def _run_all(
        self,
        candidates: list[UsernameCandidate],
        cancel_event: Event,
        progress: ProgressCallback | None,
    ) -> list[Finding]:
        sites = self._sites or {}
        maigret_search = self._maigret_search
        if not sites or maigret_search is None:
            self.prepare()
            sites = self._sites or {}
            maigret_search = self._maigret_search

        logger = logging.getLogger("osint_engine.maigret")
        logger.addHandler(logging.NullHandler())
        all_findings: list[Finding] = []
        grand_total = max(len(sites) * len(candidates), 1)
        supports_partial_output = "output_container" in inspect.signature(maigret_search).parameters

        for index, candidate in enumerate(candidates):
            if cancel_event.is_set():
                break

            notifier = _ProgressNotifier(
                self.info.key,
                len(sites),
                progress,
                identifier=candidate.value,
                offset=index * len(sites),
                grand_total=grand_total,
                cancel_event=cancel_event,
            )
            partial_results: dict[str, Any] = {}
            search_kwargs: dict[str, Any] = {
                "username": candidate.value,
                "site_dict": sites,
                "logger": logger,
                "query_notify": notifier,
                "timeout": self.timeout,
                "is_parsing_enabled": True,
                "max_connections": 40,
                "no_progressbar": True,
            }
            if supports_partial_output:
                search_kwargs["output_container"] = partial_results

            task = asyncio.create_task(maigret_search(**search_kwargs))
            watcher = asyncio.create_task(self._cancel_watcher(task, cancel_event))
            try:
                results = await task
            except asyncio.CancelledError:
                results = partial_results
            finally:
                watcher.cancel()

            results = results or partial_results
            self._report_runs.append((candidate.value, "username", results))
            all_findings.extend(self._to_findings(candidate, results))

            if cancel_event.is_set():
                break

        return all_findings

    @staticmethod
    def _to_findings(
        candidate: UsernameCandidate,
        results: dict[str, Any],
    ) -> list[Finding]:
        findings: list[Finding] = []
        for site_name, result in results.items():
            status = result.get("status")
            try:
                found = bool(status and status.is_found())
            except Exception:
                found = False
            if not found:
                continue

            # Maigret almacena el enriquecimiento de perfil en el objeto status.
            # Se conserva el fallback superior para tolerar cambios menores del
            # proveedor sin perder compatibilidad.
            status_ids_data = getattr(status, "ids_data", None) if status else None
            ids_data = status_ids_data or result.get("ids_data") or {}
            profile_image = MaigretAdapter._first_text(ids_data.get("image"))

            evidence = {
                "http_status": result.get("http_status"),
                "rank": result.get("rank"),
                "url_main": result.get("url_main"),
                "query_time": getattr(status, "query_time", None),
                "tags": json_safe(getattr(status, "tags", None) or result.get("tags") or []),
                "ids_data": json_safe(ids_data),
                "profile_image_url": profile_image,
                "identifier_checked": candidate.value,
            }
            findings.append(
                Finding(
                    finding_id=str(uuid.uuid4()),
                    entity_type="social_account",
                    value=str(result.get("url_user") or candidate.value),
                    platform=str(site_name),
                    source_engine="maigret",
                    source_url=str(result.get("url_user") or ""),
                    confidence=0.92,
                    status="confirmed_profile",
                    relation="same_username",
                    parent_value=candidate.value,
                    evidence=evidence,
                )
            )
        return findings

    @staticmethod
    def _first_text(value: Any) -> str:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, str) and item.strip():
                    return item.strip()
        return ""

    @staticmethod
    async def _cancel_watcher(task: asyncio.Task, cancel_event: Event) -> None:
        while not task.done():
            if cancel_event.is_set():
                task.cancel()
                return
            await asyncio.sleep(0.15)
