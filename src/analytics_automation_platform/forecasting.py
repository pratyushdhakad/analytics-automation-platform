"""Leakage-safe seasonal and driver-aware forecasting primitives."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from .history import commercial_event


DRIVER_COLUMNS = (
    "total_marketing_spend_usd",
    "affiliate_revenue_usd",
    "stockout_rate",
)
CHANNEL_COLUMNS = (
    "paid_search_spend_usd",
    "paid_social_spend_usd",
    "retargeting_spend_usd",
    "email_spend_usd",
)
EVENT_NAMES = ("monthly_promotion", "summer_event", "holiday_peak")
SCALED_FEATURE_INDEXES = (1, 10, 11, 12)


@dataclass(frozen=True)
class DriverRegressionModel:
    target: str
    coefficients: tuple[float, ...]
    means: dict[int, float]
    scales: dict[int, float]
    interval_radius: float

    def predict(self, row: dict[str, str], time_index: int, horizon_day: int) -> tuple[float, float, float]:
        features = feature_vector(row, time_index, self.means, self.scales)
        point = max(0.0, sum(weight * value for weight, value in zip(self.coefficients, features)))
        radius = self.interval_radius * math.sqrt(1.0 + 0.35 * max(horizon_day - 1, 0) / 90.0)
        return point, max(0.0, point - radius), point + radius


def feature_vector(
    row: dict[str, str],
    time_index: int,
    means: dict[int, float] | None = None,
    scales: dict[int, float] | None = None,
) -> list[float]:
    day = date.fromisoformat(row["activity_date"])
    day_of_year = day.timetuple().tm_yday
    values = [
        1.0,
        time_index / 365.25,
        math.sin(2.0 * math.pi * day_of_year / 365.25),
        math.cos(2.0 * math.pi * day_of_year / 365.25),
    ]
    values.extend(1.0 if day.weekday() == weekday else 0.0 for weekday in range(6))
    values.extend(float(row[column]) for column in DRIVER_COLUMNS)
    values.extend(1.0 if row["event_name"] == event else 0.0 for event in EVENT_NAMES)
    if means and scales:
        for index in SCALED_FEATURE_INDEXES:
            values[index] = (values[index] - means[index]) / scales[index]
    return values


def fit_driver_regression(
    rows: list[dict[str, str]],
    target: str,
    ridge_lambda: float,
    interval_probability: float,
) -> DriverRegressionModel:
    raw_features = [feature_vector(row, index) for index, row in enumerate(rows)]
    means: dict[int, float] = {}
    scales: dict[int, float] = {}
    for feature_index in SCALED_FEATURE_INDEXES:
        values = [row[feature_index] for row in raw_features]
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        means[feature_index] = mean
        scales[feature_index] = math.sqrt(variance) or 1.0
    features = [
        [
            (value - means[index]) / scales[index]
            if index in SCALED_FEATURE_INDEXES
            else value
            for index, value in enumerate(row)
        ]
        for row in raw_features
    ]
    actuals = [float(row[target]) for row in rows]
    coefficients = _ridge_coefficients(features, actuals, ridge_lambda)
    residuals = [
        actual - sum(weight * value for weight, value in zip(coefficients, row))
        for row, actual in zip(features, actuals)
    ]
    radius = _quantile([abs(value) for value in residuals], interval_probability)
    return DriverRegressionModel(
        target=target,
        coefficients=tuple(coefficients),
        means=means,
        scales=scales,
        interval_radius=radius,
    )


def seasonal_naive_forecast(
    history: list[dict[str, str]],
    target: str,
    forecast_index: int,
    horizon_day: int,
    season_length: int,
    interval_probability: float,
) -> tuple[float, float, float]:
    reference_index = forecast_index - season_length
    if reference_index < 0 or reference_index >= len(history):
        raise ValueError("Seasonal reference must exist inside the available history")
    point = float(history[reference_index][target])
    errors = [
        abs(float(history[index][target]) - float(history[index - season_length][target]))
        for index in range(season_length, len(history))
    ]
    radius = _quantile(errors, interval_probability)
    radius *= math.sqrt(1.0 + 0.35 * max(horizon_day - 1, 0) / 90.0)
    return point, max(0.0, point - radius), point + radius


def build_future_driver_plan(history: list[dict[str, str]], horizon_days: int) -> list[dict[str, str]]:
    """Create an explicit future driver plan from 52-week seasonality and recent pacing."""
    last_date = date.fromisoformat(history[-1]["activity_date"])
    by_date = {row["activity_date"]: row for row in history}
    growth: dict[str, float] = {}
    for column in (*CHANNEL_COLUMNS, "affiliate_revenue_usd"):
        recent = sum(float(row[column]) for row in history[-28:])
        prior = sum(float(row[column]) for row in history[-392:-364])
        ratio = recent / prior if prior else 1.0
        growth[column] = min(1.25, max(0.85, ratio))

    plan: list[dict[str, str]] = []
    for offset in range(1, horizon_days + 1):
        forecast_date = last_date + timedelta(days=offset)
        reference_date = forecast_date - timedelta(days=364)
        reference = by_date[reference_date.isoformat()]
        event_name, _ = commercial_event(forecast_date)
        channels = {
            column: float(reference[column]) * growth[column]
            for column in CHANNEL_COLUMNS
        }
        formatted_channels = {
            column: f"{value:.2f}" for column, value in channels.items()
        }
        plan.append(
            {
                "activity_date": forecast_date.isoformat(),
                "total_marketing_spend_usd": f"{sum(float(value) for value in formatted_channels.values()):.2f}",
                **formatted_channels,
                "affiliate_revenue_usd": f"{float(reference['affiliate_revenue_usd']) * growth['affiliate_revenue_usd']:.2f}",
                "stockout_rate": reference["stockout_rate"],
                "event_name": event_name,
                "driver_plan_method": "52_week_pattern_with_recent_pacing",
            }
        )
    return plan


def _ridge_coefficients(features: list[list[float]], actuals: list[float], penalty: float) -> list[float]:
    width = len(features[0])
    matrix = [[0.0 for _ in range(width)] for _ in range(width)]
    vector = [0.0 for _ in range(width)]
    for row, actual in zip(features, actuals):
        for left in range(width):
            vector[left] += row[left] * actual
            for right in range(width):
                matrix[left][right] += row[left] * row[right]
    for index in range(1, width):
        matrix[index][index] += penalty
    return _solve_linear_system(matrix, vector)


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float]:
    width = len(vector)
    augmented = [row[:] + [value] for row, value in zip(matrix, vector)]
    for column in range(width):
        pivot = max(range(column, width), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("Forecast design matrix is singular")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        pivot_value = augmented[column][column]
        augmented[column] = [value / pivot_value for value in augmented[column]]
        for row in range(width):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor == 0:
                continue
            augmented[row] = [
                current - factor * pivot_current
                for current, pivot_current in zip(augmented[row], augmented[column])
            ]
    return [augmented[row][-1] for row in range(width)]


def _quantile(values: list[float], probability: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight
