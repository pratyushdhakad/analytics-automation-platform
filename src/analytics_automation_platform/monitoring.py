"""Turn out-of-sample champion forecasts into operational health evidence."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .ingestion import write_json


STATUS_RANK = {"HEALTHY": 0, "WATCH": 1, "CRITICAL": 2}
TARGET_LABELS = {
    "net_revenue_usd": "Net revenue",
    "shipped_revenue_usd": "Shipped revenue",
}


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def validate_monitoring_config(config: dict[str, Any]) -> None:
    windows = config.get("evaluation_window_days")
    primary = config.get("primary_window_days")
    thresholds = config.get("thresholds", {})
    if not isinstance(windows, list) or not windows or windows != sorted(set(windows)):
        raise ValueError("evaluation_window_days must be unique ascending integers")
    if not all(isinstance(value, int) and value > 0 for value in windows):
        raise ValueError("evaluation_window_days must be unique ascending integers")
    if primary not in windows:
        raise ValueError("primary_window_days must be an evaluation window")

    wape = thresholds.get("wape_pct", {})
    bias = thresholds.get("absolute_bias_pct", {})
    coverage = thresholds.get("interval_coverage_pct", {})
    if not 0 <= wape.get("watch", -1) < wape.get("critical", -1):
        raise ValueError("WAPE thresholds must increase from watch to critical")
    if not 0 <= bias.get("watch", -1) < bias.get("critical", -1):
        raise ValueError("bias thresholds must increase from watch to critical")
    if not 0 <= coverage.get("critical_below", -1) < coverage.get("watch_below", -1) <= 100:
        raise ValueError("coverage thresholds must increase from critical to watch")


def _metrics(rows: list[dict[str, str]]) -> dict[str, float | int]:
    actual = sum(float(row["actual"]) for row in rows)
    error = sum(float(row["error"]) for row in rows)
    absolute_error = sum(abs(float(row["error"])) for row in rows)
    covered = sum(
        float(row["lower_bound"]) <= float(row["actual"]) <= float(row["upper_bound"])
        for row in rows
    )
    return {
        "observation_count": len(rows),
        "wape_pct": round(absolute_error / actual * 100, 2),
        "bias_pct": round(error / actual * 100, 2),
        "interval_coverage_pct": round(covered / len(rows) * 100, 2),
    }


def _status_and_alerts(
    target: str,
    metrics: dict[str, float | int],
    thresholds: dict[str, dict[str, float]],
) -> tuple[str, list[dict[str, str | float]]]:
    checks = (
        (
            "wape_pct",
            float(metrics["wape_pct"]),
            thresholds["wape_pct"]["watch"],
            thresholds["wape_pct"]["critical"],
            "above",
        ),
        (
            "absolute_bias_pct",
            abs(float(metrics["bias_pct"])),
            thresholds["absolute_bias_pct"]["watch"],
            thresholds["absolute_bias_pct"]["critical"],
            "above",
        ),
        (
            "interval_coverage_pct",
            float(metrics["interval_coverage_pct"]),
            thresholds["interval_coverage_pct"]["watch_below"],
            thresholds["interval_coverage_pct"]["critical_below"],
            "below",
        ),
    )
    alerts: list[dict[str, str | float]] = []
    status = "HEALTHY"
    for metric, value, watch, critical, direction in checks:
        if direction == "above":
            severity = "CRITICAL" if value >= critical else "WATCH" if value >= watch else "HEALTHY"
            threshold = critical if severity == "CRITICAL" else watch
        else:
            severity = "CRITICAL" if value < critical else "WATCH" if value < watch else "HEALTHY"
            threshold = critical if severity == "CRITICAL" else watch
        if STATUS_RANK[severity] > STATUS_RANK[status]:
            status = severity
        if severity == "HEALTHY":
            continue

        if metric == "absolute_bias_pct":
            direction_label = "under-predicting" if float(metrics["bias_pct"]) < 0 else "over-predicting"
            message = (
                f"{TARGET_LABELS[target]} is {direction_label} actuals by {value:.2f}%; "
                "review plan, backlog, and capacity assumptions before the next refresh."
            )
        elif metric == "wape_pct":
            message = (
                f"{TARGET_LABELS[target]} WAPE is {value:.2f}%; investigate recent driver "
                "changes before using the forecast for commitments."
            )
        else:
            message = (
                f"{TARGET_LABELS[target]} interval coverage is {value:.2f}%; "
                "recalibrate uncertainty before relying on the current range."
            )
        alerts.append(
            {
                "target": target,
                "metric": metric,
                "severity": severity,
                "value": round(value, 2),
                "threshold": round(threshold, 2),
                "message": message,
            }
        )
    return status, alerts


def build_forecast_monitoring(root: Path) -> dict[str, Any]:
    config = _read_json(root / "config" / "monitoring.json")
    validate_monitoring_config(config)
    evaluation = _read_json(root / "artifacts" / "forecast_evaluation.json")
    backtest = _read_csv(root / "artifacts" / "forecast_backtest.csv")

    latest_origin = max(row["origin_date"] for row in backtest)
    champion_rows = [
        row
        for row in backtest
        if row["origin_date"] == latest_origin
        and evaluation["champions"].get(row["target"]) == row["model"]
    ]

    targets: dict[str, Any] = {}
    alerts: list[dict[str, str | float]] = []
    for target, champion in evaluation["champions"].items():
        rows = sorted(
            (row for row in champion_rows if row["target"] == target),
            key=lambda row: int(row["horizon_day"]),
        )
        if len(rows) < config["primary_window_days"]:
            raise ValueError(f"insufficient monitoring observations for {target}")
        windows = {
            f"{days}_days": _metrics(rows[:days])
            for days in config["evaluation_window_days"]
        }
        primary = windows[f"{config['primary_window_days']}_days"]
        status, target_alerts = _status_and_alerts(target, primary, config["thresholds"])
        targets[target] = {
            "label": TARGET_LABELS[target],
            "champion": champion,
            "status": status,
            "windows": windows,
        }
        alerts.extend(target_alerts)

    overall_status = max(
        (target["status"] for target in targets.values()),
        key=lambda value: STATUS_RANK[value],
    )
    alerts.sort(key=lambda alert: (-STATUS_RANK[str(alert["severity"])], str(alert["target"]), str(alert["metric"])))
    monitoring = {
        "monitor_version": config["monitor_version"],
        "method": "latest rolling-origin champion holdout",
        "origin_date": latest_origin,
        "observed_through": max(row["forecast_date"] for row in champion_rows),
        "primary_window_days": config["primary_window_days"],
        "overall_status": overall_status,
        "thresholds": config["thresholds"],
        "targets": targets,
        "alerts": alerts,
        "alert_count": len(alerts),
    }
    write_json(root / "artifacts" / "forecast_monitoring.json", monitoring)
    _write_alerts(root / "artifacts" / "forecast_alerts.csv", alerts)
    return monitoring


def _write_alerts(path: Path, alerts: list[dict[str, str | float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["target", "metric", "severity", "value", "threshold", "message"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(alerts)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    monitoring = build_forecast_monitoring(root)
    print(
        f"Forecast monitoring {monitoring['overall_status']}: "
        f"{monitoring['alert_count']} alerts through {monitoring['observed_through']}"
    )


if __name__ == "__main__":
    main()
