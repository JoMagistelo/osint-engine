from __future__ import annotations

import asyncio
import logging
import uuid
from importlib.resources import files
from threading import Event
from typing import Any

from .base import AdapterInfo, ProgressCallback
from ..models import Finding, InvestigationSeed, json_safe
from ..normalization import conservative_alias_candidates


class _ProgressNotifier:
    def __init__(
        self,
        engine_key: str,
        total: int,
        callback: ProgressCallback | None,
    ) -> None:
        self.engine_key = engine_key
        self.total = max(total, 1)
        self.callback = callback
        self.checked = 0
        self.found = 0

    def update(self, status: Any, similar_search: bool = False) -> None:
        self.checked += 1
        try:
            if status.is_found():
                self.found += 1
        except Exception:
            pass
        if self.callback:
            self.callback(
                self.engine_key,
                min(self.checked, self.total),
                self.total,
                f"{self.found} coincidencias",
            )


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
        usernames: list[tuple[str, str, float]] = []
        if seed.username:
            usernames.append((seed.username, "provided_username", 1.0))
        if seed.derive_aliases:
            for alias in conservative_alias_candidates(seed):
                if alias != seed.username:
                    usernames.append((alias, "derived_email_local_part", 0.35))

        if not usernames:
            if progress:
                progress(self.info.key, 0, 0, "Sin usuario para consultar")
            return []

        return asyncio.run(self._run_all(usernames, cancel_event, progress))

    async def _run_all(
        self,
        usernames: list[tuple[str, str, float]],
        cancel_event: Event,
        progress: ProgressCallback | None,
    ) -> list[Finding]:
        try:
            from maigret import search as maigret_search
            from maigret.sites import MaigretDatabase
        except Exception as exc:
            raise RuntimeError(
                "Maigret no está instalado correctamente. Ejecute pip install -e \".[desktop]\"."
            ) from exc

        data_path = files("maigret").joinpath("resources", "data.json")
        database = MaigretDatabase().load_from_path(str(data_path))
        sites = database.ranked_sites_dict(
            top=self.top_sites,
            excluded_tags=["nsfw", "dating"],
        )
        logger = logging.getLogger("osint_engine.maigret")
        logger.addHandler(logging.NullHandler())
        all_findings: list[Finding] = []

        for username, origin, seed_confidence in usernames:
            if cancel_event.is_set():
                break
            notifier = _ProgressNotifier(self.info.key, len(sites), progress)
            task = asyncio.create_task(
                maigret_search(
                    username=username,
                    site_dict=sites,
                    logger=logger,
                    query_notify=notifier,
                    timeout=self.timeout,
                    is_parsing_enabled=True,
                    max_connections=40,
                    no_progressbar=True,
                )
            )
            watcher = asyncio.create_task(self._cancel_watcher(task, cancel_event))
            try:
                results = await task
            except asyncio.CancelledError:
                break
            finally:
                watcher.cancel()

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
                    "seed_origin": origin,
                    "identifier_checked": username,
                }
                all_findings.append(
                    Finding(
                        finding_id=str(uuid.uuid4()),
                        entity_type="social_account",
                        value=str(result.get("url_user") or username),
                        platform=str(site_name),
                        source_engine="maigret",
                        source_url=str(result.get("url_user") or ""),
                        confidence=round(0.92 * seed_confidence, 2),
                        status="confirmed_profile" if seed_confidence >= 0.9 else "candidate_profile",
                        relation="same_username" if seed_confidence >= 0.9 else "candidate_username",
                        parent_value=username,
                        evidence=evidence,
                    )
                )
        return all_findings

    @staticmethod
    async def _cancel_watcher(task: asyncio.Task, cancel_event: Event) -> None:
        while not task.done():
            if cancel_event.is_set():
                task.cancel()
                return
            await asyncio.sleep(0.15)
