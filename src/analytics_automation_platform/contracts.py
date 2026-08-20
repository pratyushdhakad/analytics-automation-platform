"""Source-contract loading and deterministic validation."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CheckResult:
    source: str
    check: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "source": self.source,
            "check": self.check,
            "status": self.status,
            "detail": self.detail,
        }


class ContractViolation(ValueError):
    """Raised when a source violates its declared contract."""

    def __init__(self, checks: list[CheckResult]):
        self.checks = checks
        failures = [check.detail for check in checks if check.status == "FAIL"]
        super().__init__("; ".join(failures))


def load_registry(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        registry = json.load(handle)
    if not registry.get("contract_version") or not registry.get("sources"):
        raise ValueError("Registry requires contract_version and at least one source")
    return registry


def load_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{path} has no header")
        return list(reader.fieldnames), list(reader)


def _parse(value: str, data_type: str) -> object:
    if data_type == "string":
        return value
    if data_type == "date":
        return date.fromisoformat(value)
    if data_type == "datetime":
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    if data_type == "decimal":
        return Decimal(value)
    if data_type == "integer":
        return int(value)
    raise ValueError(f"Unsupported type: {data_type}")


def validate_source(
    source: dict[str, Any],
    headers: list[str],
    rows: list[dict[str, str]],
    as_of: datetime,
) -> list[CheckResult]:
    name = source["name"]
    checks: list[CheckResult] = []
    expected = list(source["columns"])
    missing = [column for column in expected if column not in headers]
    unexpected = [column for column in headers if column not in expected]
    schema_ok = not missing and not unexpected
    checks.append(
        CheckResult(
            name,
            "schema",
            "PASS" if schema_ok else "FAIL",
            f"{len(expected)} expected columns present"
            if schema_ok
            else f"missing={missing}; unexpected={unexpected}",
        )
    )

    validation_errors: list[str] = []
    parsed_by_column: dict[str, list[object]] = {column: [] for column in expected}
    if schema_ok:
        for row_number, row in enumerate(rows, start=2):
            for column, rule in source["columns"].items():
                value = row.get(column, "")
                if rule.get("required") and value == "":
                    validation_errors.append(f"row {row_number} {column} is blank")
                    continue
                if value == "":
                    continue
                try:
                    parsed = _parse(value, rule["type"])
                except (ValueError, InvalidOperation):
                    validation_errors.append(
                        f"row {row_number} {column} is not {rule['type']}"
                    )
                    continue
                parsed_by_column[column].append(parsed)
                accepted = rule.get("accepted_values")
                if accepted is not None and value not in accepted:
                    validation_errors.append(
                        f"row {row_number} {column}={value!r} is not accepted"
                    )
                if "min" in rule and parsed < Decimal(str(rule["min"])):
                    validation_errors.append(
                        f"row {row_number} {column}={value} is below {rule['min']}"
                    )
    checks.append(
        CheckResult(
            name,
            "values",
            "PASS" if not validation_errors else "FAIL",
            f"{len(rows)} rows satisfy required, type, domain, and range rules"
            if not validation_errors
            else " | ".join(validation_errors),
        )
    )

    keys = [tuple(row.get(column, "") for column in source["primary_key"]) for row in rows]
    duplicate_count = len(keys) - len(set(keys))
    checks.append(
        CheckResult(
            name,
            "primary_key",
            "PASS" if duplicate_count == 0 else "FAIL",
            f"{len(keys)} unique keys"
            if duplicate_count == 0
            else f"{duplicate_count} duplicate keys",
        )
    )

    freshness_field = source["freshness_field"]
    timestamps = parsed_by_column.get(freshness_field, [])
    latest = max(timestamps) if timestamps else None
    lag_hours = (as_of - latest).total_seconds() / 3600 if latest else None
    freshness_ok = (
        lag_hours is not None
        and lag_hours >= 0
        and lag_hours <= source["max_lag_hours"]
    )
    checks.append(
        CheckResult(
            name,
            "freshness",
            "PASS" if freshness_ok else "FAIL",
            f"latest={latest.isoformat().replace('+00:00', 'Z')}; lag_hours={lag_hours:.2f}"
            if latest and lag_hours is not None
            else "no valid freshness timestamp",
        )
    )
    return checks


def parse_as_of(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def validate_foreign_keys(
    registry: dict[str, Any], datasets: dict[str, list[dict[str, str]]]
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    for source in registry["sources"]:
        for foreign_key in source.get("foreign_keys", []):
            local_columns = foreign_key["columns"]
            reference_name = foreign_key["references_source"]
            reference_columns = foreign_key["references_columns"]
            reference_keys = {
                tuple(row[column] for column in reference_columns)
                for row in datasets[reference_name]
            }
            missing = [
                tuple(row[column] for column in local_columns)
                for row in datasets[source["name"]]
                if tuple(row[column] for column in local_columns) not in reference_keys
            ]
            checks.append(
                CheckResult(
                    source["name"],
                    f"foreign_key:{','.join(local_columns)}->{reference_name}",
                    "PASS" if not missing else "FAIL",
                    f"all {len(datasets[source['name']])} keys resolve"
                    if not missing
                    else f"missing references={missing}",
                )
            )
    return checks

