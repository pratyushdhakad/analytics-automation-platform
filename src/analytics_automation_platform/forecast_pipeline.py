"""Day 3 backtesting, champion selection, and future forecast artifacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .evaluation import evaluate_backtest, rolling_origin_backtest
from .forecasting import (
    build_future_driver_plan,
    fit_driver_regression,
    seasonal_naive_forecast,
)
from .ingestion import write_json, write_rows


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def run_forecast_pipeline(root: Path) -> dict[str, Any]:
    history = _read_csv(root / "artifacts" / "marts" / "daily_revenue_metrics.csv")
    with (root / "config" / "forecasting.json").open(encoding="utf-8") as handle:
        config = json.load(handle)
    backtest, origins = rolling_origin_backtest(history, config)
    evaluation = evaluate_backtest(backtest, history, origins, config)
    driver_plan = build_future_driver_plan(history, config["future_horizon_days"])
    future_forecasts = _future_forecasts(history, driver_plan, evaluation, config)
    summary = _forecast_summary(history, future_forecasts, evaluation, config)

    write_rows(
        root / "artifacts" / "forecast_backtest.csv",
        list(backtest[0]),
        [{key: str(value) for key, value in row.items()} for row in backtest],
    )
    write_json(root / "artifacts" / "forecast_evaluation.json", evaluation)
    write_rows(
        root / "artifacts" / "forecast_driver_plan.csv",
        list(driver_plan[0]),
        driver_plan,
    )
    write_rows(
        root / "artifacts" / "revenue_forecast.csv",
        list(future_forecasts[0]),
        [{key: str(value) for key, value in row.items()} for row in future_forecasts],
    )
    write_json(root / "artifacts" / "forecast_summary.json", summary)
    return summary


def _future_forecasts(
    history: list[dict[str, str]],
    plan: list[dict[str, str]],
    evaluation: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    fitted = {
        target: fit_driver_regression(
            history,
            target,
            config["ridge_lambda"],
            config["prediction_interval"],
        )
        for target in config["targets"]
        if evaluation["champions"][target] == "driver_regression"
    }
    for target in config["targets"]:
        champion = evaluation["champions"][target]
        for horizon_day, plan_row in enumerate(plan, start=1):
            row_index = len(history) + horizon_day - 1
            if champion == "driver_regression":
                point, lower, upper = fitted[target].predict(
                    plan_row, row_index, horizon_day
                )
            else:
                point, lower, upper = seasonal_naive_forecast(
                    history,
                    target,
                    row_index,
                    horizon_day,
                    config["season_length_days"],
                    config["prediction_interval"],
                )
            output.append(
                {
                    "forecast_date": plan_row["activity_date"],
                    "horizon_day": horizon_day,
                    "target": target,
                    "model": champion,
                    "forecast": round(point, 2),
                    "lower_bound": round(lower, 2),
                    "upper_bound": round(upper, 2),
                    "planned_marketing_spend_usd": plan_row["total_marketing_spend_usd"],
                    "planned_affiliate_revenue_usd": plan_row["affiliate_revenue_usd"],
                    "planned_stockout_rate": plan_row["stockout_rate"],
                    "planned_event": plan_row["event_name"],
                }
            )
    return output


def _forecast_summary(
    history: list[dict[str, str]],
    forecasts: list[dict[str, object]],
    evaluation: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    horizons: dict[str, dict[str, object]] = {}
    for horizon in config["evaluation_horizons_days"]:
        target_summaries: dict[str, object] = {}
        for target in config["targets"]:
            target_forecasts = [
                row
                for row in forecasts
                if row["target"] == target and int(row["horizon_day"]) <= horizon
            ]
            historical = sum(float(row[target]) for row in history[-horizon:])
            point = sum(float(row["forecast"]) for row in target_forecasts)
            target_summaries[target] = {
                "point_forecast_usd": round(point, 2),
                "daily_lower_bound_sum_usd": round(
                    sum(float(row["lower_bound"]) for row in target_forecasts), 2
                ),
                "daily_upper_bound_sum_usd": round(
                    sum(float(row["upper_bound"]) for row in target_forecasts), 2
                ),
                "prior_period_actual_usd": round(historical, 2),
                "change_vs_prior_period_pct": round(
                    100.0 * (point - historical) / historical, 2
                ),
            }
        horizons[f"{horizon}_days"] = target_summaries
    return {
        "forecast_version": config["forecast_version"],
        "as_of_date": history[-1]["activity_date"],
        "forecast_start_date": forecasts[0]["forecast_date"],
        "forecast_end_date": forecasts[-1]["forecast_date"],
        "horizon_days": config["future_horizon_days"],
        "champions": evaluation["champions"],
        "driver_plan_method": "52_week_pattern_with_recent_pacing",
        "prediction_interval": config["prediction_interval"],
        "interval_note": "Totals sum daily marginal bounds and are not joint period intervals.",
        "horizons": horizons,
    }


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    summary = run_forecast_pipeline(root)
    print(
        "Forecast complete through {forecast_end_date}; champions={champions}".format(
            **summary
        )
    )


if __name__ == "__main__":
    main()

