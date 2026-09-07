from __future__ import annotations

import uuid
from threading import Event

from .adapters import MaigretAdapter, ProgressCallback, SpiderFootAdapter
from .correlation import deduplicate_findings
from .models import Finding, Investigation, InvestigationSeed, utc_now_iso
from .normalization import conservative_alias_candidates, normalize_seed, validate_seed


class InvestigationEngine:
    def __init__(self, maigret_top_sites: int = 250) -> None:
        self.adapters = [
            MaigretAdapter(top_sites=maigret_top_sites),
            SpiderFootAdapter(),
        ]

    def run(
        self,
        seed: InvestigationSeed,
        cancel_event: Event,
        progress: ProgressCallback | None = None,
    ) -> Investigation:
        normalized = normalize_seed(seed)
        errors = validate_seed(normalized)
        if errors:
            raise ValueError(" ".join(errors))

        investigation = Investigation(
            investigation_id=str(uuid.uuid4()),
            seed=normalized,
            status="running",
        )
        investigation.findings.extend(self._seed_findings(normalized))

        if normalized.derive_aliases:
            for alias in conservative_alias_candidates(normalized):
                investigation.findings.append(
                    Finding(
                        finding_id=str(uuid.uuid4()),
                        entity_type="username_candidate",
                        value=alias,
                        source_engine="osint-engine",
                        confidence=0.35,
                        status="hypothesis",
                        relation="derived_from_email",
                        parent_value=normalized.email,
                        evidence={
                            "rule": "email_local_part",
                            "warning": "Hipótesis; no prueba identidad.",
                        },
                    )
                )

        for adapter in self.adapters:
            if cancel_event.is_set():
                investigation.status = "cancelled"
                break
            if not adapter.info.enabled:
                continue
            try:
                investigation.findings.extend(adapter.run(normalized, cancel_event, progress))
            except Exception as exc:
                investigation.notes.append(f"{adapter.info.name}: {exc}")

        investigation.findings = deduplicate_findings(investigation.findings)
        if cancel_event.is_set():
            investigation.status = "cancelled"
        elif investigation.notes:
            investigation.status = "completed_with_warnings"
        else:
            investigation.status = "completed"
        investigation.finished_at = utc_now_iso()
        return investigation

    @staticmethod
    def _seed_findings(seed: InvestigationSeed) -> list[Finding]:
        findings: list[Finding] = []
        for kind, value in seed.non_empty_identifiers().items():
            findings.append(
                Finding(
                    finding_id=str(uuid.uuid4()),
                    entity_type=kind,
                    value=value,
                    source_engine="operator_input",
                    confidence=1.0,
                    status="provided",
                    relation="seed",
                    evidence={"case_id": seed.case_id},
                )
            )
        return findings
