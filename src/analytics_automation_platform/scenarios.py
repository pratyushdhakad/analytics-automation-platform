"""Conditional growth scenarios layered onto champion forecast baselines."""

from __future__ import annotations

from typing import Any

from .forecasting import CHANNEL_COLUMNS, DriverRegressionModel


def validate_scenario_config(config: dict[str, Any]) -> None:
    scenarios = config.get("scenarios", [])
    identifiers = [scenario.get("scenario_id") for scenario in scenarios]
    if not scenarios or len(identifiers) != len(set(identifiers)):
        raise ValueError("Scenario identifiers must be present and unique")
    if identifiers.count(config.get("base_scenario")) != 1:
        raise ValueError("The configured base scenario must exist exactly once")
    expected_channels = {
        column.removesuffix("_spend_usd") for column in CHANNEL_COLUMNS
    }
    for scenario in scenarios:
        multipliers = scenario.get("channel_spend_multipliers", {})
        if set(multipliers) != expected_channels:
            raise ValueError(
                f"Scenario {scenario['scenario_id']} must define every channel"
            )
        values = [
            *multipliers.values(),
            scenario.get("affiliate_multiplier"),
            scenario.get("promotion_multiplier"),
            scenario.get("fulfillment_capacity_multiplier"),
        ]
        if any(value is None or float(value) <= 0 for value in values):
            raise ValueError(
                f"Scenario {scenario['scenario_id']} multipliers must be positive"
            )


def apply_scenarios(
    base_plan: list[dict[str, str]],
    base_forecasts: list[dict[str, str]],
    models: dict[str, DriverRegressionModel],
    scenario_config: dict[str, Any],
    history_length: int,
) -> list[dict[str, object]]:
    validate_scenario_config(scenario_config)
    forecast_lookup = {
        (row["target"], int(row["horizon_day"])): row for row in base_forecasts
    }
    output: list[dict[str, object]] = []
    for scenario in scenario_config["scenarios"]:
        for horizon_day, base_row in enumerate(base_plan, start=1):
            scenario_row = scenario_driver_row(base_row, scenario)
            time_index = history_length + horizon_day - 1
            calculated: dict[str, dict[str, Any]] = {}
            for target, model in models.items():
                base_forecast = forecast_lookup[(target, horizon_day)]
                base_driver_point = model.predict(base_row, time_index, horizon_day)[0]
                scenario_driver_point = model.predict(
                    scenario_row, time_index, horizon_day
                )[0]
                event_increment = _event_increment(
                    model, scenario_row, time_index, horizon_day
                )
                scenario_driver_point += (
                    float(scenario["promotion_multiplier"]) - 1.0
                ) * event_increment
                delta = scenario_driver_point - base_driver_point
                point = max(0.0, float(base_forecast["forecast"]) + delta)
                lower = max(0.0, float(base_forecast["lower_bound"]) + delta)
                upper = max(lower, float(base_forecast["upper_bound"]) + delta)
                calculated[target] = {
                    "base_forecast": base_forecast,
                    "delta": delta,
                    "point": point,
                    "lower": lower,
                    "upper": upper,
                }

            capacity = float(scenario["fulfillment_capacity_multiplier"])
            shipped = calculated["shipped_revenue_usd"]
            if capacity >= 1.0:
                capacity_delta = (capacity - 1.0) * max(
                    calculated["net_revenue_usd"]["point"] - shipped["point"],
                    0.0,
                )
            else:
                capacity_delta = (capacity - 1.0) * shipped["point"]
            shipped["delta"] += capacity_delta
            shipped["point"] = max(0.0, shipped["point"] + capacity_delta)
            shipped["lower"] = max(0.0, shipped["lower"] + capacity_delta)
            shipped["upper"] = max(
                shipped["lower"], shipped["upper"] + capacity_delta
            )

            for target, result in calculated.items():
                base_forecast = result["base_forecast"]
                output.append(
                    {
                        "scenario_id": scenario["scenario_id"],
                        "scenario_label": scenario["label"],
                        "forecast_date": scenario_row["activity_date"],
                        "horizon_day": horizon_day,
                        "target": target,
                        "baseline_model": base_forecast["model"],
                        "scenario_method": "champion_baseline_plus_driver_delta",
                        "forecast": round(result["point"], 2),
                        "lower_bound": round(result["lower"], 2),
                        "upper_bound": round(result["upper"], 2),
                        "delta_vs_base_usd": round(result["delta"], 2),
                        "planned_marketing_spend_usd": scenario_row[
                            "total_marketing_spend_usd"
                        ],
                        "planned_affiliate_revenue_usd": scenario_row[
                            "affiliate_revenue_usd"
                        ],
                        "planned_stockout_rate": scenario_row["stockout_rate"],
                        "planned_event": scenario_row["event_name"],
                        "fulfillment_capacity_multiplier": capacity,
                    }
                )
    return output


def scenario_driver_row(
    base_row: dict[str, str], scenario: dict[str, Any]
) -> dict[str, str]:
    row = dict(base_row)
    channel_values: dict[str, float] = {}
    for column in CHANNEL_COLUMNS:
        channel = column.removesuffix("_spend_usd")
        channel_values[column] = float(base_row[column]) * float(
            scenario["channel_spend_multipliers"][channel]
        )
    formatted_channels = {
        column: f"{value:.2f}" for column, value in channel_values.items()
    }
    row.update(formatted_channels)
    row["total_marketing_spend_usd"] = (
        f"{sum(float(value) for value in formatted_channels.values()):.2f}"
    )
    row["affiliate_revenue_usd"] = (
        f"{float(base_row['affiliate_revenue_usd']) * float(scenario['affiliate_multiplier']):.2f}"
    )
    return row


def _event_increment(
    model: DriverRegressionModel,
    row: dict[str, str],
    time_index: int,
    horizon_day: int,
) -> float:
    if row["event_name"] == "none":
        return 0.0
    event_point = model.predict(row, time_index, horizon_day)[0]
    without_event = dict(row)
    without_event["event_name"] = "none"
    no_event_point = model.predict(without_event, time_index, horizon_day)[0]
    return max(0.0, event_point - no_event_point)
