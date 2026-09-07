from __future__ import annotations

import asyncio
import inspect
import logging
import uuid
from importlib.resources import files
from threading import Event
from typing import Any

from .base import AdapterInfo, ProgressCallback
from ..models import Finding, InvestigationSeed, json_safe
from ..normalization import UsernameCandidate, username_search_candidates


class _ProgressNotifier:
    """Implementa el contrato de notificación usado por Maigret 0.6.5+."""

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

    def __init__(self, top_sites: int = 250, timeout: int = 15) -> None:
        self.top_sites = top_sites
        self.timeout = timeout

    def run(
        self,
        seed: InvestigationSeed,
        cancel_event: Event,
        progress: ProgressCallback | None = None,
    ) -> list[Finding]:
        candidates = username_search_candidates(seed)

        if not candidates:
            if progress:
                progress(self.info.key, 0, 0, "Sin alias compatible para consultar")
            return []

        return asyncio.run(self._run_all(candidates, cancel_event, progress))

    async def _run_all(
        self,
        candidates: list[UsernameCandidate],
        cancel_event: Event,
        progress: ProgressCallback | None,
    ) -> list[Finding]:
        try:
            from maigret import search as maigret_search
            from maigret.sites import MaigretDatabase
        except Exception as exc:
            raise RuntimeError(
                'Maigret no está instalado correctamente. Ejecute pip install -e ".[desktop]".'
            ) from exc

        data_path = files("maigret").joinpath("resources", "data.json")
        database = MaigretDatabase().load_from_path(str(data_path))
        sites = database.ranked_sites_dict(top=self.top_sites)

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

            evidence = {
                "http_status": result.get("http_status"),
                "rank": result.get("rank"),
                "ids_data": json_safe(result.get("ids_data") or {}),
                "seed_origin": candidate.origin,
                "identifier_checked": candidate.value,
                "candidate_confidence": candidate.confidence,
            }
            findings.append(
                Finding(
                    finding_id=str(uuid.uuid4()),
                    entity_type="social_account",
                    value=str(result.get("url_user") or candidate.value),
                    platform=str(site_name),
                    source_engine="maigret",
                    source_url=str(result.get("url_user") or ""),
                    confidence=round(0.92 * candidate.confidence, 2),
                    status=(
                        "confirmed_profile"
                        if candidate.origin == "provided_username"
                        else "candidate_profile"
                    ),
                    relation=(
                        "same_username"
                        if candidate.origin == "provided_username"
                        else candidate.relation
                    ),
                    parent_value=candidate.parent_value or candidate.value,
                    evidence=evidence,
                )
            )
        return findings

    @staticmethod
    async def _cancel_watcher(task: asyncio.Task, cancel_event: Event) -> None:
        while not task.done():
            if cancel_event.is_set():
                task.cancel()
                return
            await asyncio.sleep(0.15)
