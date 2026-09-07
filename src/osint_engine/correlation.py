from __future__ import annotations

from collections import defaultdict

from .models import Finding, InvestigationSeed


def deduplicate_findings(findings: list[Finding]) -> list[Finding]:
    best: dict[tuple[str, str, str], Finding] = {}
    for finding in findings:
        key = (
            finding.entity_type.casefold(),
            finding.platform.casefold(),
            finding.value.casefold(),
        )
        previous = best.get(key)
        if previous is None or finding.confidence > previous.confidence:
            best[key] = finding
    return list(best.values())


def platform_summary(findings: list[Finding]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for finding in findings:
        if finding.platform:
            counts[finding.platform] += 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold())))


def confidence_label(value: float) -> str:
    if value >= 0.90:
        return "Alta"
    if value >= 0.65:
        return "Media"
    return "Baja"


def seed_node_label(seed: InvestigationSeed) -> str:
    return seed.person_name or seed.username or seed.email or seed.phone or "Investigación"
