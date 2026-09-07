from osint_engine.correlation import confidence_label, deduplicate_findings
from osint_engine.models import Finding


def test_deduplicate_keeps_highest_confidence():
    low = Finding("1", "social_account", "https://x/u", "maigret", platform="X", confidence=0.3)
    high = Finding("2", "social_account", "https://x/u", "maigret", platform="X", confidence=0.9)
    result = deduplicate_findings([low, high])
    assert len(result) == 1
    assert result[0].confidence == 0.9


def test_confidence_labels():
    assert confidence_label(0.95) == "Alta"
    assert confidence_label(0.7) == "Media"
    assert confidence_label(0.2) == "Baja"
