from pathlib import Path

from osint_engine.exporters import export_all
from osint_engine.models import Finding, Investigation, InvestigationSeed


def test_export_all(tmp_path: Path):
    inv = Investigation("abc12345", InvestigationSeed(username="demo", case_id="CASO-1"))
    inv.findings.append(Finding("f1", "username", "demo", "operator_input", confidence=1.0))
    paths = export_all(inv, tmp_path)
    assert {p.suffix for p in paths} == {".json", ".csv", ".graphml"}
    assert all(p.exists() for p in paths)
