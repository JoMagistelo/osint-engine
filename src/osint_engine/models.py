from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    return str(value)


@dataclass(slots=True)
class InvestigationSeed:
    person_name: str = ""
    username: str = ""
    email: str = ""
    phone: str = ""
    case_id: str = ""
    derive_aliases: bool = False

    def non_empty_identifiers(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "person_name": self.person_name,
                "username": self.username,
                "email": self.email,
                "phone": self.phone,
            }.items()
            if value
        }


@dataclass(slots=True)
class Finding:
    finding_id: str
    entity_type: str
    value: str
    source_engine: str
    source_url: str = ""
    platform: str = ""
    confidence: float = 0.0
    status: str = "observed"
    relation: str = "discovered_by"
    parent_value: str = ""
    retrieved_at: str = field(default_factory=utc_now_iso)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return json_safe(asdict(self))


@dataclass(slots=True)
class Investigation:
    investigation_id: str
    seed: InvestigationSeed
    started_at: str = field(default_factory=utc_now_iso)
    finished_at: str | None = None
    status: str = "created"
    findings: list[Finding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["findings"] = [f.to_dict() for f in self.findings]
        return json_safe(payload)
