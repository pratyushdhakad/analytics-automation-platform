"""Build the static executive dashboard data contract for GitHub Pages."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .ingestion import write_json


FEATURED_SCENARIOS = ("base_plan", "upside", "downside")


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_dashboard_data(root: Path) -> dict[str, Any]:
    forecast = _read_json(root / "artifacts" / "forecast_summary.json")
    evaluation = _read_json(root / "artifacts" / "forecast_evaluation.json")
    scenarios = _read_json(root / "artifacts" / "scenario_summary.json")
    ingestion = _read_json(root / "artifacts" / "ingestion_manifest.json")
    metrics = _read_json(root / "artifacts" / "metric_summary.json")
    monitoring = _read_json(root / "artifacts" / "forecast_monitoring.json")
    scenario_rows = _read_csv(root / "artifacts" / "scenario_forecasts.csv")

    daily: dict[str, dict[str, list[dict[str, object]]]] = {
        scenario_id: {
            "net_revenue_usd": [],
            "shipped_revenue_usd": [],
        }
        for scenario_id in FEATURED_SCENARIOS
    }
    for row in scenario_rows:
        scenario_id = row["scenario_id"]
        if scenario_id not in FEATURED_SCENARIOS:
            continue
        daily[scenario_id][row["target"]].append(
            {
                "date": row["forecast_date"],
                "day": int(row["horizon_day"]),
                "forecast": float(row["forecast"]),
                "lower": float(row["lower_bound"]),
                "upper": float(row["upper_bound"]),
            }
        )

    model_health: dict[str, Any] = {}
    for target, champion in evaluation["champions"].items():
        score = evaluation["metrics"][target][champion]["91_days"]
        model_health[target] = {
            "champion": champion,
            "wape_pct": score["wape_pct"],
            "bias_pct": score["bias_pct"],
            "interval_coverage_pct": score["interval_coverage_pct"],
            "mase": score["mase"],
        }

    scenario_cards = []
    for scenario_id, scenario in scenarios["scenarios"].items():
        scenario_cards.append(
            {
                "scenario_id": scenario_id,
                "label": scenario["label"],
                "description": scenario["description"],
                "assumptions": scenario["assumptions"],
                "horizons": scenario["horizons"],
            }
        )

    dashboard = {
        "dashboard_version": "1.0.0",
        "title": "Revenue Forecasting Control Tower",
        "as_of_date": forecast["as_of_date"],
        "forecast_start_date": forecast["forecast_start_date"],
        "forecast_end_date": forecast["forecast_end_date"],
        "horizon_days": forecast["horizon_days"],
        "quality": {
            "data_gate": ingestion["publish_gate"],
            "source_count": ingestion["source_count"],
            "source_row_count": ingestion["total_rows"],
            "forecast_ready_days": metrics["day_count"],
            "metric_reconciliation": metrics["reconciliation_status"],
            "metric_check_count": metrics["quality_check_count"],
        },
        "model_health": model_health,
        "monitoring": monitoring,
        "scenario_method": scenarios["method"],
        "interpretation": scenarios["interpretation"],
        "scenarios": scenario_cards,
        "daily": daily,
    }
    write_json(root / "site" / "data" / "dashboard.json", dashboard)
    return dashboard


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    dashboard = build_dashboard_data(root)
    print(
        f"Dashboard data ready through {dashboard['forecast_end_date']}: "
        f"{len(dashboard['scenarios'])} scenarios"
    )


if __name__ == "__main__":
    main()
