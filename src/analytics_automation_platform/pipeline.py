"""Deterministic revenue analytics pipeline entry point."""

from pathlib import Path

from .forecast_pipeline import run_forecast_pipeline
from .history import generate_history
from .ingestion import run_ingestion
from .metrics import build_daily_metrics
from .scenario_pipeline import run_scenario_pipeline


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    history = generate_history(root)
    manifest = run_ingestion(root)
    metric_summary = build_daily_metrics(root)
    forecast_summary = run_forecast_pipeline(root)
    scenario_summary = run_scenario_pipeline(root)
    print(
        "Revenue data gate {gate}: {sources} sources, {rows} rows, "
        "{days} forecast-ready days, run {run_id}".format(
            gate=manifest["publish_gate"],
            sources=manifest["source_count"],
            rows=manifest["total_rows"],
            days=history["day_count"],
            run_id=manifest["run_id"],
        )
    )
    print(
        "Metric reconciliation {status}: {checks} checks, latest 28-day net revenue ${revenue:,.2f}".format(
            status=metric_summary["reconciliation_status"],
            checks=metric_summary["quality_check_count"],
            revenue=metric_summary["latest_28_days"]["net_revenue_usd"],
        )
    )
    print(
        "Forecast through {forecast_end_date}: champions={champions}".format(
            **forecast_summary
        )
    )
    print(
        f"Scenario analysis: {scenario_summary['scenario_count']} plans across "
        f"{scenario_summary['horizon_days'][-1]} days"
    )


if __name__ == "__main__":
    main()
