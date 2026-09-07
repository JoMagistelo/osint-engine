from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Callable, Protocol

from ..models import Finding, InvestigationSeed


ProgressCallback = Callable[[str, int, int, str], None]


@dataclass(slots=True)
class AdapterInfo:
    key: str
    name: str
    enabled: bool
    description: str


class OsintAdapter(Protocol):
    info: AdapterInfo

    def run(
        self,
        seed: InvestigationSeed,
        cancel_event: Event,
        progress: ProgressCallback | None = None,
    ) -> list[Finding]: ...
