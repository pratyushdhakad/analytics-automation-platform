"""Append-only forecast vintages and point-in-time actual evaluation."""

from __future__ import annotations

import csv
import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from .ingestion import sha256_file, write_json, write_rows


VINTAGE_FIELDS = [
    "vintage_id",
    "vintage_type",
    "origin_date",
    "issued_at_utc",
    "forecast_date",
    "horizon_day",
    "target",
    "model",
    "model_version",
    "forecast_version",
    "forecast",
    "lower_bound",
    "upper_bound",
]

OBSERVATION_FIELDS = VINTAGE_FIELDS + [
    "actual_available_at_utc",
    "actual",
    "error",
    "observation_status",
    "evaluated_as_of_utc",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(f"timestamp must be UTC: {value}")
    return parsed


def _combine_utc(day: str, clock: str) -> str:
    parsed_time = time.fromisoformat(clock.removesuffix("Z"))
    parsed = datetime.combine(date.fromisoformat(day), parsed_time, tzinfo=timezone.utc)
    return parsed.isoformat().replace("+00:00", "Z")


def validate_vintage_config(
    config: dict[str, Any], forecast_config: dict[str, Any]
) -> None:
    if not config.get("vintage_contract_version"):
        raise ValueError("vintage_contract_version is required")
    if not isinstance(config.get("actual_availability_lag_days"), int):
        raise ValueError("actual_availability_lag_days must be an integer")
    if config["actual_availability_lag_days"] < 0:
        raise ValueError("actual_availability_lag_days cannot be negative")
    _parse_utc(config["evaluation_as_of_utc"])
    _combine_utc("2000-01-01", config["issue_time_utc"])
    _combine_utc("2000-01-01", config["actual_availability_time_utc"])
    missing = set(forecast_config["models"]) - set(config.get("model_versions", {}))
    if missing:
        raise ValueError(f"model_versions missing: {sorted(missing)}")


def _vintage_id(origin_date: str, forecast_version: str) -> str:
    version = forecast_version.replace(".", "_")
    return f"vintage-{origin_date.replace('-', '')}-f{version}"


def _vintage_row(
    row: dict[str, Any],
    origin_date: str,
    vintage_type: str,
    forecast_config: dict[str, Any],
    vintage_config: dict[str, Any],
) -> dict[str, str]:
    model = str(row["model"])
    return {
        "vintage_id": _vintage_id(origin_date, forecast_config["forecast_version"]),
        "vintage_type": vintage_type,
        "origin_date": origin_date,
        "issued_at_utc": _combine_utc(origin_date, vintage_config["issue_time_utc"]),
        "forecast_date": str(row["forecast_date"]),
        "horizon_day": str(row["horizon_day"]),
        "target": str(row["target"]),
        "model": model,
        "model_version": str(vintage_config["model_versions"][model]),
        "forecast_version": str(forecast_config["forecast_version"]),
        "forecast": str(row["forecast"]),
        "lower_bound": str(row["lower_bound"]),
        "upper_bound": str(row["upper_bound"]),
    }


def build_vintage_rows(
    backtest: list[dict[str, str]],
    future_forecast: list[dict[str, str]],
    champions: dict[str, str],
    current_origin: str,
    forecast_config: dict[str, Any],
    vintage_config: dict[str, Any],
) -> list[dict[str, str]]:
    rows = [
        _vintage_row(
            row,
            row["origin_date"],
            "historical_backtest",
            forecast_config,
            vintage_config,
        )
        for row in backtest
        if champions.get(row["target"]) == row["model"]
    ]
    rows.extend(
        _vintage_row(
            row,
            current_origin,
            "current_plan",
            forecast_config,
            vintage_config,
        )
        for row in future_forecast
    )
    rows.sort(
        key=lambda row: (
            row["issued_at_utc"],
            row["target"],
            row["forecast_date"],
        )
    )
    return rows


def publish_append_only(path: Path, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Append new identities and reject changes to an identity already published."""

    def key(row: dict[str, str]) -> tuple[str, str, str]:
        return row["vintage_id"], row["target"], row["forecast_date"]

    incoming = {key(row): row for row in rows}
    if len(incoming) != len(rows):
        raise ValueError("duplicate forecast vintage identity")
    existing = _read_csv(path) if path.exists() else []
    existing_by_key = {key(row): row for row in existing}
    for identity in existing_by_key.keys() & incoming.keys():
        if existing_by_key[identity] != incoming[identity]:
            raise ValueError(
                "immutable forecast vintage conflict for " + "|".join(identity)
            )
    merged = existing + [
        row for identity, row in incoming.items() if identity not in existing_by_key
    ]
    merged.sort(
        key=lambda row: (
            row["issued_at_utc"],
            row["target"],
            row["forecast_date"],
        )
    )
    write_rows(path, VINTAGE_FIELDS, merged)
    return merged


def build_actual_facts(
    history: list[dict[str, str]], vintage_config: dict[str, Any], targets: list[str]
) -> list[dict[str, str]]:
    facts: list[dict[str, str]] = []
    lag = timedelta(days=vintage_config["actual_availability_lag_days"])
    for row in history:
        available_day = date.fromisoformat(row["activity_date"]) + lag
        available_at = _combine_utc(
            available_day.isoformat(), vintage_config["actual_availability_time_utc"]
        )
        for target in targets:
            facts.append(
                {
                    "forecast_date": row["activity_date"],
                    "target": target,
                    "actual": row[target],
                    "actual_available_at_utc": available_at,
                }
            )
    return facts


def join_vintages_as_of(
    vintages: list[dict[str, str]],
    actual_facts: list[dict[str, str]],
    as_of_utc: str,
) -> list[dict[str, str]]:
    """Return only forecasts issued by as-of time and reveal only available actuals."""

    as_of = _parse_utc(as_of_utc)
    actual_by_key = {
        (row["forecast_date"], row["target"]): row for row in actual_facts
    }
    observations: list[dict[str, str]] = []
    for vintage in vintages:
        issued_at = _parse_utc(vintage["issued_at_utc"])
        if issued_at > as_of:
            continue
        if vintage["forecast_date"] <= vintage["origin_date"]:
            raise ValueError("forecast date must be after its vintage origin")
        actual = actual_by_key.get((vintage["forecast_date"], vintage["target"]))
        observation = dict(vintage)
        observation.update(
            {
                "actual_available_at_utc": "",
                "actual": "",
                "error": "",
                "observation_status": "PENDING",
                "evaluated_as_of_utc": as_of_utc,
            }
        )
        if actual and _parse_utc(actual["actual_available_at_utc"]) <= as_of:
            if issued_at >= _parse_utc(actual["actual_available_at_utc"]):
                raise ValueError("actual was available before forecast issuance")
            actual_value = float(actual["actual"])
            observation.update(
                {
                    "actual_available_at_utc": actual["actual_available_at_utc"],
                    "actual": actual["actual"],
                    "error": f"{float(vintage['forecast']) - actual_value:.2f}",
                    "observation_status": "OBSERVED",
                }
            )
        observations.append(observation)
    return observations


def build_forecast_vintages(root: Path) -> dict[str, Any]:
    forecast_config_path = root / "config" / "forecasting.json"
    vintage_config_path = root / "config" / "vintages.json"
    evaluation_path = root / "artifacts" / "forecast_evaluation.json"
    forecast_config = _read_json(forecast_config_path)
    vintage_config = _read_json(vintage_config_path)
    validate_vintage_config(vintage_config, forecast_config)
    evaluation = _read_json(evaluation_path)
    summary = _read_json(root / "artifacts" / "forecast_summary.json")
    backtest_path = root / "artifacts" / "forecast_backtest.csv"
    future_path = root / "artifacts" / "revenue_forecast.csv"
    mart_path = root / "artifacts" / "marts" / "daily_revenue_metrics.csv"
    backtest = _read_csv(backtest_path)
    future = _read_csv(future_path)
    history = _read_csv(mart_path)

    candidate_rows = build_vintage_rows(
        backtest,
        future,
        evaluation["champions"],
        summary["as_of_date"],
        forecast_config,
        vintage_config,
    )
    vintage_path = root / "artifacts" / "forecast_vintages.csv"
    vintages = publish_append_only(vintage_path, candidate_rows)
    facts = build_actual_facts(history, vintage_config, forecast_config["targets"])
    observations = join_vintages_as_of(
        vintages, facts, vintage_config["evaluation_as_of_utc"]
    )
    observation_path = root / "artifacts" / "forecast_vintage_observations.csv"
    write_rows(observation_path, OBSERVATION_FIELDS, observations)

    observed = [row for row in observations if row["observation_status"] == "OBSERVED"]
    pending = [row for row in observations if row["observation_status"] == "PENDING"]
    origins = sorted({row["origin_date"] for row in vintages})
    manifest = {
        "vintage_contract_version": vintage_config["vintage_contract_version"],
        "evaluation_as_of_utc": vintage_config["evaluation_as_of_utc"],
        "append_only_status": "PASS",
        "point_in_time_status": "PASS",
        "vintage_count": len(origins),
        "origins": origins,
        "current_vintage_id": _vintage_id(
            summary["as_of_date"], forecast_config["forecast_version"]
        ),
        "forecast_row_count": len(vintages),
        "observed_row_count": len(observed),
        "pending_row_count": len(pending),
        "observed_through": max(row["forecast_date"] for row in observed),
        "source_sha256": {
            "forecast_backtest": sha256_file(backtest_path),
            "forecast_contract": sha256_file(forecast_config_path),
            "forecast_evaluation": sha256_file(evaluation_path),
            "revenue_forecast": sha256_file(future_path),
            "daily_revenue_metrics": sha256_file(mart_path),
            "vintage_contract": sha256_file(vintage_config_path),
        },
    }
    write_json(root / "artifacts" / "forecast_vintage_manifest.json", manifest)
    return manifest


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    manifest = build_forecast_vintages(root)
    print(
        f"Forecast vintages PASS: {manifest['vintage_count']} runs, "
        f"{manifest['observed_row_count']} observed rows, "
        f"{manifest['pending_row_count']} pending rows"
    )


if __name__ == "__main__":
    main()
