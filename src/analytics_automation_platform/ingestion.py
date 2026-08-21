"""Validated ingestion and evidence generation."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from .contracts import (
    CheckResult,
    ContractViolation,
    load_registry,
    load_rows,
    parse_as_of,
    validate_foreign_keys,
    validate_source,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_rows(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_run_id(contract_version: str, as_of: str) -> str:
    token = hashlib.sha256(f"{contract_version}|{as_of}".encode()).hexdigest()[:10]
    return f"fixture-{as_of[:10].replace('-', '')}-{token}"


def run_ingestion(root: Path) -> dict[str, Any]:
    registry_path = root / "config" / "sources.json"
    registry = load_registry(registry_path)
    as_of_text = registry["fixture_as_of"]
    as_of = parse_as_of(as_of_text)
    datasets: dict[str, list[dict[str, str]]] = {}
    headers_by_source: dict[str, list[str]] = {}
    source_entries: list[dict[str, Any]] = []
    checks: list[CheckResult] = []

    for source in registry["sources"]:
        source_path = root / source["path"]
        headers, rows = load_rows(source_path)
        datasets[source["name"]] = rows
        headers_by_source[source["name"]] = headers
        checks.extend(validate_source(source, headers, rows, as_of))
        latest = max(row[source["freshness_field"]] for row in rows)
        source_entries.append(
            {
                "name": source["name"],
                "path": source["path"],
                "primary_key": source["primary_key"],
                "row_count": len(rows),
                "latest_record_at": latest,
                "sha256": sha256_file(source_path),
            }
        )

    checks.extend(validate_foreign_keys(registry, datasets))
    failed = [check for check in checks if check.status == "FAIL"]
    if failed:
        raise ContractViolation(checks)

    raw_dir = root / "artifacts" / "raw"
    for source in registry["sources"]:
        name = source["name"]
        write_rows(raw_dir / f"{name}.csv", headers_by_source[name], datasets[name])

    quality_report = {
        "contract_version": registry["contract_version"],
        "fixture_as_of": as_of_text,
        "status": "PASS",
        "check_count": len(checks),
        "failed_check_count": 0,
        "checks": [check.to_dict() for check in checks],
    }
    manifest = {
        "run_id": build_run_id(registry["contract_version"], as_of_text),
        "run_type": "deterministic_fixture",
        "contract_version": registry["contract_version"],
        "fixture_as_of": as_of_text,
        "publish_gate": "PASS",
        "source_count": len(source_entries),
        "total_rows": sum(source["row_count"] for source in source_entries),
        "sources": source_entries,
    }
    write_json(root / "artifacts" / "quality_report.json", quality_report)
    write_json(root / "artifacts" / "ingestion_manifest.json", manifest)
    return manifest


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    manifest = run_ingestion(root)
    print(
        "Ingestion gate {publish_gate}: {source_count} sources, {total_rows} rows, "
        "run {run_id}".format(**manifest)
    )


if __name__ == "__main__":
    main()
