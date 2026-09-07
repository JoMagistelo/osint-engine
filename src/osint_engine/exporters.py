from __future__ import annotations

import csv
import json
from pathlib import Path
from xml.sax.saxutils import escape

from .models import Investigation


def default_export_dir() -> Path:
    path = Path.home() / "Documents" / "OSINT_Engine" / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_basename(investigation: Investigation) -> str:
    case_id = "".join(ch for ch in investigation.seed.case_id if ch.isalnum() or ch in "-_" )
    return case_id or investigation.investigation_id[:8]


def export_json(investigation: Investigation, directory: Path | None = None) -> Path:
    directory = directory or default_export_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"osint_{safe_basename(investigation)}.json"
    path.write_text(
        json.dumps(investigation.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def export_csv(investigation: Investigation, directory: Path | None = None) -> Path:
    directory = directory or default_export_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"osint_{safe_basename(investigation)}.csv"
    fields = [
        "finding_id", "entity_type", "value", "platform", "source_engine",
        "source_url", "confidence", "status", "relation", "parent_value", "retrieved_at",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for finding in investigation.findings:
            row = finding.to_dict()
            writer.writerow({key: row.get(key, "") for key in fields})
    return path


def export_graphml(investigation: Investigation, directory: Path | None = None) -> Path:
    directory = directory or default_export_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"osint_{safe_basename(investigation)}.graphml"

    root_label = investigation.seed.person_name or "Investigación"
    nodes = [("root", root_label, "investigation")]
    edges: list[tuple[str, str, str]] = []
    value_to_id: dict[str, str] = {}
    for idx, finding in enumerate(investigation.findings, start=1):
        node_id = f"n{idx}"
        value_to_id.setdefault(finding.value, node_id)
        nodes.append((node_id, finding.value, finding.entity_type))
        parent_id = value_to_id.get(finding.parent_value, "root")
        edges.append((parent_id, node_id, finding.relation))

    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
        '  <key id="label" for="node" attr.name="label" attr.type="string"/>',
        '  <key id="type" for="node" attr.name="type" attr.type="string"/>',
        '  <key id="relation" for="edge" attr.name="relation" attr.type="string"/>',
        '  <graph id="G" edgedefault="directed">',
    ]
    for node_id, label, node_type in nodes:
        xml.append(
            f'    <node id="{escape(node_id)}"><data key="label">{escape(label)}</data>'
            f'<data key="type">{escape(node_type)}</data></node>'
        )
    for idx, (source, target, relation) in enumerate(edges, start=1):
        xml.append(
            f'    <edge id="e{idx}" source="{escape(source)}" target="{escape(target)}">'
            f'<data key="relation">{escape(relation)}</data></edge>'
        )
    xml.extend(["  </graph>", "</graphml>"])
    path.write_text("\n".join(xml), encoding="utf-8")
    return path


def export_all(investigation: Investigation, directory: Path | None = None) -> list[Path]:
    directory = directory or default_export_dir()
    return [
        export_json(investigation, directory),
        export_csv(investigation, directory),
        export_graphml(investigation, directory),
    ]
