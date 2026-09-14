import json
from pathlib import Path

from osint_engine.exporters import export_all, export_json
from osint_engine.models import Finding, Investigation, InvestigationSeed


def test_export_all_without_maigret_runtime_keeps_core_formats(tmp_path: Path):
    inv = Investigation("abc12345", InvestigationSeed(username="demo", case_id="CASO-1"))
    inv.findings.append(Finding("f1", "username", "demo", "operator_input", confidence=1.0))
    paths = export_all(inv, tmp_path)
    assert {p.suffix for p in paths} == {".json", ".csv", ".graphml"}
    assert all(p.exists() for p in paths)


def test_json_does_not_serialize_runtime_objects(tmp_path: Path):
    inv = Investigation("abc12345", InvestigationSeed(username="demo"))
    inv.runtime_data["maigret_runs"] = [("demo", "username", {"raw": object()})]
    path = export_json(inv, tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "runtime_data" not in payload


def test_export_all_adds_native_maigret_html_when_results_exist(tmp_path: Path, monkeypatch):
    inv = Investigation("abc12345", InvestigationSeed(username="demo", case_id="CASO-2"))
    inv.runtime_data["maigret_runs"] = [("demo", "username", {"GitHub": {}})]

    monkeypatch.setattr("maigret.report.generate_report_context", lambda runs: {"runs": runs})

    def fake_save(filename, context):
        Path(filename).write_text("<html>maigret</html>", encoding="utf-8")

    monkeypatch.setattr("maigret.report.save_html_report", fake_save)
    paths = export_all(inv, tmp_path)

    assert any(path.name.startswith("maigret_") and path.suffix == ".html" for path in paths)
    assert all(path.exists() for path in paths)
