"""Rolling-origin forecast evaluation and comparable error metrics."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from .forecasting import fit_driver_regression, seasonal_naive_forecast


def rolling_origin_backtest(
    rows: list[dict[str, str]], config: dict[str, Any]
) -> tuple[list[dict[str, object]], list[int]]:
    horizon = config["future_horizon_days"]
    settings = config["backtest"]
    last_origin = len(rows) - horizon
    first_origin = last_origin - settings["step_days"] * (settings["origin_count"] - 1)
    if first_origin < settings["minimum_training_days"]:
        raise ValueError("Not enough history for the configured rolling origins")
    origins = [
        first_origin + settings["step_days"] * index
        for index in range(settings["origin_count"])
    ]
    records: list[dict[str, object]] = []
    for target in config["targets"]:
        for origin in origins:
            training = rows[:origin]
            driver_model = fit_driver_regression(
                training,
                target,
                config["ridge_lambda"],
                config["prediction_interval"],
            )
            origin_date = training[-1]["activity_date"]
            for horizon_day in range(1, horizon + 1):
                row_index = origin + horizon_day - 1
                actual_row = rows[row_index]
                actual = float(actual_row[target])
                seasonal = seasonal_naive_forecast(
                    training,
                    target,
                    row_index,
                    horizon_day,
                    config["season_length_days"],
                    config["prediction_interval"],
                )
                driver = driver_model.predict(actual_row, row_index, horizon_day)
                for model_name, values in (
                    ("seasonal_naive", seasonal),
                    ("driver_regression", driver),
                ):
                    point, lower, upper = values
                    records.append(
                        {
                            "origin_date": origin_date,
                            "forecast_date": actual_row["activity_date"],
                            "horizon_day": horizon_day,
                            "target": target,
                            "model": model_name,
                            "actual": round(actual, 2),
                            "forecast": round(point, 2),
                            "lower_bound": round(lower, 2),
                            "upper_bound": round(upper, 2),
                            "error": round(point - actual, 2),
                        }
                    )
    return records, origins


def evaluate_backtest(
    records: list[dict[str, object]],
    history: list[dict[str, str]],
    origins: list[int],
    config: dict[str, Any],
) -> dict[str, Any]:
    metrics: dict[str, dict[str, dict[str, object]]] = defaultdict(dict)
    champions: dict[str, str] = {}
    for target in config["targets"]:
        scale_history = history[: origins[0]]
        seasonal_scale = _seasonal_scale(
            scale_history, target, config["season_length_days"]
        )
        for model in config["models"]:
            model_records = [
                record
                for record in records
                if record["target"] == target and record["model"] == model
            ]
            windows: dict[str, object] = {}
            for horizon in config["evaluation_horizons_days"]:
                window_records = [
                    record
                    for record in model_records
                    if int(record["horizon_day"]) <= horizon
                ]
                windows[f"{horizon}_days"] = _accuracy_metrics(
                    window_records, seasonal_scale
                )
            metrics[target][model] = windows
        final_window = f"{config['evaluation_horizons_days'][-1]}_days"
        champions[target] = min(
            config["models"],
            key=lambda model: metrics[target][model][final_window]["wape_pct"],
        )
    return {
        "forecast_version": config["forecast_version"],
        "evaluation_method": "rolling_origin",
        "driver_backtest_mode": config["backtest"]["driver_mode"],
        "origin_count": len(origins),
        "origin_dates": [history[index - 1]["activity_date"] for index in origins],
        "horizon_days": config["future_horizon_days"],
        "prediction_interval": config["prediction_interval"],
        "champions": champions,
        "metrics": metrics,
    }


def _accuracy_metrics(
    records: list[dict[str, object]], seasonal_scale: float
) -> dict[str, object]:
    actuals = [float(record["actual"]) for record in records]
    forecasts = [float(record["forecast"]) for record in records]
    errors = [forecast - actual for forecast, actual in zip(forecasts, actuals)]
    absolute_errors = [abs(error) for error in errors]
    squared_errors = [error**2 for error in errors]
    total_actual = sum(abs(actual) for actual in actuals)
    covered = sum(
        1
        for record in records
        if float(record["lower_bound"]) <= float(record["actual"]) <= float(record["upper_bound"])
    )
    return {
        "observation_count": len(records),
        "mae": round(sum(absolute_errors) / len(records), 2),
        "rmse": round(math.sqrt(sum(squared_errors) / len(records)), 2),
        "wape_pct": round(100.0 * sum(absolute_errors) / total_actual, 2),
        "mase": round((sum(absolute_errors) / len(records)) / seasonal_scale, 3),
        "bias_pct": round(100.0 * sum(errors) / total_actual, 2),
        "interval_coverage_pct": round(100.0 * covered / len(records), 2),
    }


def _seasonal_scale(
    rows: list[dict[str, str]], target: str, season_length: int
) -> float:
    errors = [
        abs(float(rows[index][target]) - float(rows[index - season_length][target]))
        for index in range(season_length, len(rows))
    ]
    return sum(errors) / len(errors) or 1.0

