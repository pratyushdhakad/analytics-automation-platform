"""Day 4 scenario artifacts and executive comparison tables."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .forecasting import fit_driver_regression
from .ingestion import write_json, write_rows
from .scenarios import apply_scenarios


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def run_scenario_pipeline(root: Path) -> dict[str, Any]:
    history = _read_csv(root / "artifacts" / "marts" / "daily_revenue_metrics.csv")
    plan = _read_csv(root / "artifacts" / "forecast_driver_plan.csv")
    forecasts = _read_csv(root / "artifacts" / "revenue_forecast.csv")
    with (root / "config" / "forecasting.json").open(encoding="utf-8") as handle:
        forecast_config = json.load(handle)
    with (root / "config" / "scenarios.json").open(encoding="utf-8") as handle:
        scenario_config = json.load(handle)
    models = {
        target: fit_driver_regression(
            history,
            target,
            forecast_config["ridge_lambda"],
            forecast_config["prediction_interval"],
        )
        for target in forecast_config["targets"]
    }
    scenario_rows = apply_scenarios(
        plan, forecasts, models, scenario_config, len(history)
    )
    summary, ranking = _summaries(
        scenario_rows, scenario_config, forecast_config["evaluation_horizons_days"]
    )
    write_rows(
        root / "artifacts" / "scenario_forecasts.csv",
        list(scenario_rows[0]),
        [{key: str(value) for key, value in row.items()} for row in scenario_rows],
    )
    write_json(root / "artifacts" / "scenario_summary.json", summary)
    write_rows(
        root / "artifacts" / "scenario_ranking.csv",
        list(ranking[0]),
        [{key: str(value) for key, value in row.items()} for row in ranking],
    )
    return summary


def _summaries(
    rows: list[dict[str, object]],
    config: dict[str, Any],
    horizons: list[int],
) -> tuple[dict[str, Any], list[dict[str, object]]]:
    base_id = config["base_scenario"]
    base_totals = _totals(rows, base_id, horizons[-1])
    scenario_summaries: dict[str, Any] = {}
    ranking: list[dict[str, object]] = []
    for scenario in config["scenarios"]:
        scenario_id = scenario["scenario_id"]
        horizon_summaries: dict[str, Any] = {}
        for horizon in horizons:
            totals = _totals(rows, scenario_id, horizon)
            base = _totals(rows, base_id, horizon)
            horizon_summaries[f"{horizon}_days"] = {
                "net_revenue_usd": round(totals["net_revenue_usd"], 2),
                "shipped_revenue_usd": round(totals["shipped_revenue_usd"], 2),
                "marketing_spend_usd": round(totals["marketing_spend_usd"], 2),
                "affiliate_revenue_usd": round(totals["affiliate_revenue_usd"], 2),
                "net_revenue_delta_vs_base_usd": round(
                    totals["net_revenue_usd"] - base["net_revenue_usd"], 2
                ),
                "shipped_revenue_delta_vs_base_usd": round(
                    totals["shipped_revenue_usd"] - base["shipped_revenue_usd"],
                    2,
                ),
                "marketing_spend_delta_vs_base_usd": round(
                    totals["marketing_spend_usd"] - base["marketing_spend_usd"],
                    2,
                ),
            }
        scenario_summaries[scenario_id] = {
            "label": scenario["label"],
            "description": scenario["description"],
            "assumptions": {
                key: value
                for key, value in scenario.items()
                if key not in {"scenario_id", "label", "description"}
            },
            "horizons": horizon_summaries,
        }
        final = horizon_summaries[f"{horizons[-1]}_days"]
        spend_delta = float(final["marketing_spend_delta_vs_base_usd"])
        revenue_delta = float(final["net_revenue_delta_vs_base_usd"])
        ranking.append(
            {
                "scenario_id": scenario_id,
                "scenario_label": scenario["label"],
                "net_revenue_usd": final["net_revenue_usd"],
                "net_revenue_delta_vs_base_usd": revenue_delta,
                "shipped_revenue_usd": final["shipped_revenue_usd"],
                "shipped_revenue_delta_vs_base_usd": final[
                    "shipped_revenue_delta_vs_base_usd"
                ],
                "marketing_spend_usd": final["marketing_spend_usd"],
                "marketing_spend_delta_vs_base_usd": spend_delta,
                "planning_revenue_per_incremental_spend": (
                    "" if spend_delta <= 0 else round(revenue_delta / spend_delta, 3)
                ),
            }
        )
    ranking.sort(key=lambda row: float(row["net_revenue_usd"]), reverse=True)
    return (
        {
            "scenario_version": config["scenario_version"],
            "method": "champion_baseline_plus_driver_delta",
            "base_scenario": base_id,
            "scenario_count": len(config["scenarios"]),
            "horizon_days": horizons,
            "base_91_day_net_revenue_usd": round(
                base_totals["net_revenue_usd"], 2
            ),
            "interpretation": "Conditional planning scenarios, not causal lift or ROAS estimates.",
            "scenarios": scenario_summaries,
        },
        ranking,
    )


def _totals(
    rows: list[dict[str, object]], scenario_id: str, horizon: int = 91
) -> dict[str, float]:
    selected = [
        row
        for row in rows
        if row["scenario_id"] == scenario_id and int(row["horizon_day"]) <= horizon
    ]
    by_target = {
        target: sum(
            float(row["forecast"]) for row in selected if row["target"] == target
        )
        for target in ("net_revenue_usd", "shipped_revenue_usd")
    }
    planning_rows = [row for row in selected if row["target"] == "net_revenue_usd"]
    return {
        **by_target,
        "marketing_spend_usd": sum(
            float(row["planned_marketing_spend_usd"]) for row in planning_rows
        ),
        "affiliate_revenue_usd": sum(
            float(row["planned_affiliate_revenue_usd"]) for row in planning_rows
        ),
    }


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    summary = run_scenario_pipeline(root)
    print(
        f"Scenario analysis complete: {summary['scenario_count']} plans across "
        f"{summary['horizon_days'][-1]} days"
    )


if __name__ == "__main__":
    main()
