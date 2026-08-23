"""Generate deterministic revenue, marketing, affiliate, and shipment history."""

from __future__ import annotations

import csv
import hashlib
import math
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable


AS_OF_DATE = date(2026, 8, 20)
START_DATE = date(2023, 8, 21)
UPDATED_AT = "2026-08-20T09:00:00Z"

CHANNELS = {
    "paid_search": {"base_spend": 430.0, "cpc": 1.72, "conversion_rate": 0.043},
    "paid_social": {"base_spend": 325.0, "cpc": 1.08, "conversion_rate": 0.026},
    "retargeting": {"base_spend": 155.0, "cpc": 0.82, "conversion_rate": 0.061},
    "email": {"base_spend": 42.0, "cpc": 0.18, "conversion_rate": 0.074},
}

AFFILIATES = {
    "creator_collective": {"base_orders": 6.5, "aov": 96.0, "commission_rate": 0.14},
    "cashback_network": {"base_orders": 4.3, "aov": 88.0, "commission_rate": 0.10},
    "editorial_partner": {"base_orders": 3.2, "aov": 108.0, "commission_rate": 0.12},
}


def _noise(day: date, salt: str, amplitude: float = 0.08) -> float:
    digest = hashlib.sha256(f"{day.isoformat()}|{salt}".encode()).hexdigest()
    unit = int(digest[:8], 16) / 0xFFFFFFFF
    return 1.0 + (unit * 2.0 - 1.0) * amplitude


def _round_money(value: float) -> str:
    return f"{value:.2f}"


def _days() -> Iterable[date]:
    for offset in range((AS_OF_DATE - START_DATE).days + 1):
        yield START_DATE + timedelta(days=offset)


def commercial_event(day: date) -> tuple[str, float]:
    if day.month == 11 and day.day >= 20:
        return "holiday_peak", 1.34
    if day.month == 12 and day.day <= 18:
        return "holiday_peak", 1.27
    if day.month == 7 and day.day <= 5:
        return "summer_event", 1.18
    if day.day in {14, 15, 16}:
        return "monthly_promotion", 1.11
    return "none", 1.0


def generate_history(root: Path) -> dict[str, object]:
    """Generate three forecast-ready source tables with stable output bytes."""
    source_dir = root / "data" / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    days = list(_days())
    marketing_rows: list[dict[str, str]] = []
    affiliate_rows: list[dict[str, str]] = []
    revenue_rows: list[dict[str, str]] = []
    marketing_by_day: dict[date, float] = {}
    affiliate_revenue_by_day: dict[date, float] = {}

    for index, day in enumerate(days):
        event_name, event_lift = commercial_event(day)
        annual = 1.0 + 0.18 * math.cos(2 * math.pi * (day.timetuple().tm_yday - 330) / 365.25)
        trend = 1.0 + 0.00032 * index
        total_spend = 0.0
        for channel, settings in CHANNELS.items():
            channel_event = 1.0 + (event_lift - 1.0) * (1.25 if channel != "email" else 0.7)
            spend = settings["base_spend"] * annual * trend * channel_event * _noise(day, channel)
            clicks = max(1, round(spend / settings["cpc"]))
            conversions = max(
                0,
                round(clicks * settings["conversion_rate"] * event_lift * _noise(day, f"{channel}-conversion", 0.05)),
            )
            impressions = round(clicks * (22 if channel == "paid_search" else 38))
            marketing_rows.append(
                {
                    "activity_date": day.isoformat(),
                    "channel": channel,
                    "spend_usd": _round_money(spend),
                    "impressions": str(impressions),
                    "clicks": str(clicks),
                    "attributed_orders": str(conversions),
                    "updated_at": UPDATED_AT,
                }
            )
            total_spend += spend
        marketing_by_day[day] = total_spend

        affiliate_total = 0.0
        for partner, settings in AFFILIATES.items():
            partner_factor = annual * trend * event_lift * _noise(day, partner, 0.11)
            orders = max(0, round(settings["base_orders"] * partner_factor))
            clicks = max(orders, round(orders / (0.052 if partner == "creator_collective" else 0.041)))
            revenue = orders * settings["aov"] * _noise(day, f"{partner}-aov", 0.04)
            commission = revenue * settings["commission_rate"]
            affiliate_rows.append(
                {
                    "activity_date": day.isoformat(),
                    "partner": partner,
                    "clicks": str(clicks),
                    "orders": str(orders),
                    "revenue_usd": _round_money(revenue),
                    "commission_usd": _round_money(commission),
                    "updated_at": UPDATED_AT,
                }
            )
            affiliate_total += revenue
        affiliate_revenue_by_day[day] = affiliate_total

    backlog_revenue = 0.0
    prior_gross: list[float] = []
    weekday_factors = [0.84, 0.91, 0.98, 1.02, 1.12, 1.17, 0.96]
    for index, day in enumerate(days):
        event_name, event_lift = commercial_event(day)
        annual = 1.0 + 0.18 * math.cos(2 * math.pi * (day.timetuple().tm_yday - 330) / 365.25)
        trend = 1.0 + 0.00032 * index
        baseline = 3850.0 * annual * trend * weekday_factors[day.weekday()] * event_lift
        gross = (
            baseline * _noise(day, "gross", 0.045)
            + marketing_by_day[day] * 1.85
            + affiliate_revenue_by_day[day] * 0.72
        )
        refund_base = prior_gross[-5] if len(prior_gross) >= 5 else gross
        refund_rate = 0.038 + (0.008 if event_name == "holiday_peak" else 0.0)
        refunds = refund_base * refund_rate * _noise(day, "refunds", 0.08)
        net_revenue = max(0.0, gross - refunds)
        aov = 91.0 * _noise(day, "aov", 0.035)
        orders = max(1, round(gross / aov))
        units_sold = max(orders, round(orders * 1.31 * _noise(day, "units", 0.025)))
        stockout_rate = max(
            0.0,
            min(0.16, 0.018 + (0.055 if event_name == "holiday_peak" else 0.0) + (0.018 if event_name == "monthly_promotion" else 0.0)),
        )
        weekday_capacity = [1.08, 1.08, 1.06, 1.04, 0.98, 0.55, 0.42][day.weekday()]
        seasonal_capacity = 0.90 if event_name == "holiday_peak" else 1.0
        capacity = 9000.0 * trend * weekday_capacity * seasonal_capacity
        available_to_ship = backlog_revenue + net_revenue
        shipped_revenue = min(available_to_ship, capacity)
        backlog_revenue = max(0.0, available_to_ship - shipped_revenue)
        units_shipped = max(0, round(shipped_revenue / max(aov, 1.0) * 1.31))
        revenue_rows.append(
            {
                "activity_date": day.isoformat(),
                "gross_revenue_usd": _round_money(gross),
                "refunds_usd": _round_money(refunds),
                "net_revenue_usd": _round_money(net_revenue),
                "orders": str(orders),
                "units_sold": str(units_sold),
                "shipped_revenue_usd": _round_money(shipped_revenue),
                "units_shipped": str(units_shipped),
                "ending_backlog_revenue_usd": _round_money(backlog_revenue),
                "stockout_rate": f"{stockout_rate:.4f}",
                "event_name": event_name,
                "updated_at": UPDATED_AT,
            }
        )
        prior_gross.append(gross)

    _write_csv(source_dir / "revenue_daily.csv", revenue_rows)
    _write_csv(source_dir / "marketing_daily.csv", marketing_rows)
    _write_csv(source_dir / "affiliates_daily.csv", affiliate_rows)
    return {
        "start_date": START_DATE.isoformat(),
        "end_date": AS_OF_DATE.isoformat(),
        "day_count": len(days),
        "marketing_row_count": len(marketing_rows),
        "affiliate_row_count": len(affiliate_rows),
    }


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    summary = generate_history(root)
    print(
        "Generated {day_count} revenue days from {start_date} through {end_date}".format(
            **summary
        )
    )


if __name__ == "__main__":
    main()
