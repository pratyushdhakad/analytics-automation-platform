"""Governed daily revenue metrics and reconciliation evidence."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .ingestion import write_json, write_rows


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _safe_ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def build_daily_metrics(root: Path) -> dict[str, Any]:
    raw = root / "artifacts" / "raw"
    revenue_rows = _read_rows(raw / "revenue_daily.csv")
    marketing_rows = _read_rows(raw / "marketing_daily.csv")
    affiliate_rows = _read_rows(raw / "affiliates_daily.csv")
    with (root / "config" / "metrics.json").open(encoding="utf-8") as handle:
        metric_contract = json.load(handle)

    marketing: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    affiliate: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in marketing_rows:
        day = row["activity_date"]
        spend = float(row["spend_usd"])
        marketing[day]["total_marketing_spend_usd"] += spend
        marketing[day][f"{row['channel']}_spend_usd"] += spend
        marketing[day]["marketing_attributed_orders"] += int(row["attributed_orders"])
    for row in affiliate_rows:
        day = row["activity_date"]
        affiliate[day]["affiliate_revenue_usd"] += float(row["revenue_usd"])
        affiliate[day]["affiliate_commission_usd"] += float(row["commission_usd"])
        affiliate[day]["affiliate_orders"] += int(row["orders"])

    metric_rows: list[dict[str, str]] = []
    net_by_date: dict[str, float] = {}
    for row in revenue_rows:
        day = row["activity_date"]
        gross = float(row["gross_revenue_usd"])
        refunds = float(row["refunds_usd"])
        net = float(row["net_revenue_usd"])
        shipped = float(row["shipped_revenue_usd"])
        spend = marketing[day]["total_marketing_spend_usd"]
        affiliate_revenue = affiliate[day]["affiliate_revenue_usd"]
        prior_year = date.fromisoformat(day) - timedelta(days=365)
        prior_net = net_by_date.get(prior_year.isoformat())
        yoy = _safe_ratio(net - prior_net, prior_net) * 100 if prior_net else None
        metric_rows.append(
            {
                "activity_date": day,
                "gross_revenue_usd": f"{gross:.2f}",
                "refunds_usd": f"{refunds:.2f}",
                "net_revenue_usd": f"{net:.2f}",
                "shipped_revenue_usd": f"{shipped:.2f}",
                "revenue_to_ship_gap_usd": f"{net - shipped:.2f}",
                "ending_backlog_revenue_usd": row["ending_backlog_revenue_usd"],
                "orders": row["orders"],
                "units_sold": row["units_sold"],
                "units_shipped": row["units_shipped"],
                "average_order_value_usd": f"{_safe_ratio(gross, int(row['orders'])):.2f}",
                "total_marketing_spend_usd": f"{spend:.2f}",
                "paid_search_spend_usd": f"{marketing[day]['paid_search_spend_usd']:.2f}",
                "paid_social_spend_usd": f"{marketing[day]['paid_social_spend_usd']:.2f}",
                "retargeting_spend_usd": f"{marketing[day]['retargeting_spend_usd']:.2f}",
                "email_spend_usd": f"{marketing[day]['email_spend_usd']:.2f}",
                "marketing_efficiency_ratio": f"{_safe_ratio(gross, spend):.4f}",
                "marketing_attributed_orders": str(round(marketing[day]["marketing_attributed_orders"])),
                "affiliate_revenue_usd": f"{affiliate_revenue:.2f}",
                "affiliate_commission_usd": f"{affiliate[day]['affiliate_commission_usd']:.2f}",
                "affiliate_orders": str(round(affiliate[day]["affiliate_orders"])),
                "affiliate_revenue_share": f"{_safe_ratio(affiliate_revenue, gross):.4f}",
                "net_revenue_yoy_pct": "" if yoy is None else f"{yoy:.2f}",
                "stockout_rate": row["stockout_rate"],
                "event_name": row["event_name"],
            }
        )
        net_by_date[day] = net

    checks = _reconciliation_checks(metric_rows)
    failed = [check for check in checks if check["status"] == "FAIL"]
    if failed:
        raise ValueError("Metric reconciliation failed: " + "; ".join(check["detail"] for check in failed))

    output = root / "artifacts" / "marts" / "daily_revenue_metrics.csv"
    write_rows(output, list(metric_rows[0]), metric_rows)
    latest_rows = metric_rows[-28:]
    summary = {
        "metric_contract_version": metric_contract["metric_contract_version"],
        "start_date": metric_rows[0]["activity_date"],
        "end_date": metric_rows[-1]["activity_date"],
        "day_count": len(metric_rows),
        "reconciliation_status": "PASS",
        "quality_check_count": len(checks),
        "latest_28_days": {
            "gross_revenue_usd": round(sum(float(row["gross_revenue_usd"]) for row in latest_rows), 2),
            "net_revenue_usd": round(sum(float(row["net_revenue_usd"]) for row in latest_rows), 2),
            "shipped_revenue_usd": round(sum(float(row["shipped_revenue_usd"]) for row in latest_rows), 2),
            "marketing_spend_usd": round(sum(float(row["total_marketing_spend_usd"]) for row in latest_rows), 2),
            "affiliate_revenue_usd": round(sum(float(row["affiliate_revenue_usd"]) for row in latest_rows), 2),
            "ending_backlog_revenue_usd": float(latest_rows[-1]["ending_backlog_revenue_usd"]),
        },
    }
    write_json(root / "artifacts" / "metric_summary.json", summary)
    write_json(
        root / "artifacts" / "metric_quality_report.json",
        {"status": "PASS", "check_count": len(checks), "checks": checks},
    )
    return summary


def _reconciliation_checks(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    dates = [date.fromisoformat(row["activity_date"]) for row in rows]
    expected_days = (dates[-1] - dates[0]).days + 1
    checks = [
        {
            "check": "continuous_daily_grain",
            "status": "PASS" if len(rows) == expected_days and len(set(dates)) == len(rows) else "FAIL",
            "detail": f"{len(rows)} unique daily rows across {expected_days} expected days",
        }
    ]
    definitions = [
        (
            "gross_less_refunds_equals_net",
            lambda row: abs(float(row["gross_revenue_usd"]) - float(row["refunds_usd"]) - float(row["net_revenue_usd"])) <= 0.02,
        ),
        (
            "channel_spend_equals_total",
            lambda row: abs(
                sum(
                    float(row[column])
                    for column in [
                        "paid_search_spend_usd",
                        "paid_social_spend_usd",
                        "retargeting_spend_usd",
                        "email_spend_usd",
                    ]
                )
                - float(row["total_marketing_spend_usd"])
            )
            <= 0.02,
        ),
        (
            "affiliate_revenue_is_subset_of_gross",
            lambda row: 0 <= float(row["affiliate_revenue_usd"]) <= float(row["gross_revenue_usd"]),
        ),
        (
            "shipment_gap_reconciles",
            lambda row: abs(
                float(row["net_revenue_usd"])
                - float(row["shipped_revenue_usd"])
                - float(row["revenue_to_ship_gap_usd"])
            )
            <= 0.02,
        ),
        (
            "nonnegative_operating_metrics",
            lambda row: all(
                float(row[column]) >= 0
                for column in [
                    "gross_revenue_usd",
                    "refunds_usd",
                    "net_revenue_usd",
                    "shipped_revenue_usd",
                    "total_marketing_spend_usd",
                    "affiliate_revenue_usd",
                    "ending_backlog_revenue_usd",
                ]
            ),
        ),
    ]
    for name, rule in definitions:
        failures = sum(1 for row in rows if not rule(row))
        checks.append(
            {
                "check": name,
                "status": "PASS" if failures == 0 else "FAIL",
                "detail": f"{len(rows) - failures} of {len(rows)} rows pass",
            }
        )
    return checks


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    summary = build_daily_metrics(root)
    print(
        f"Metric reconciliation {summary['reconciliation_status']}: "
        f"{summary['day_count']} forecast-ready days"
    )


if __name__ == "__main__":
    main()

