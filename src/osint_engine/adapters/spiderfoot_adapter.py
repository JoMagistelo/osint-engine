from __future__ import annotations

from threading import Event

from .base import AdapterInfo, ProgressCallback
from ..models import Finding, InvestigationSeed


class SpiderFootAdapter:
    """Integration boundary reserved for a vetted, pinned SpiderFoot runtime.

    SpiderFoot is intentionally not bundled in v0.1.0. Keeping this adapter explicit prevents
    an optional third-party engine from becoming an implicit or privileged dependency.
    """

    info = AdapterInfo(
        key="spiderfoot",
        name="SpiderFoot",
        enabled=False,
        description="Adaptador preparado; integración deshabilitada en la primera versión.",
    )

    def run(
        self,
        seed: InvestigationSeed,
        cancel_event: Event,
        progress: ProgressCallback | None = None,
    ) -> list[Finding]:
        if progress:
            progress(self.info.key, 0, 0, "No habilitado en v0.1.0")
        return []
