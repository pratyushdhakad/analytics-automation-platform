"""Deterministic revenue analytics pipeline entry point."""

from pathlib import Path

from .dashboard import build_dashboard_data
from .forecast_pipeline import run_forecast_pipeline
from .history import generate_history
from .ingestion import run_ingestion
from .metrics import build_daily_metrics
from .monitoring import build_forecast_monitoring
from .scenario_pipeline import run_scenario_pipeline
from .vintages import build_forecast_vintages


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    history = generate_history(root)
    manifest = run_ingestion(root)
    metric_summary = build_daily_metrics(root)
    forecast_summary = run_forecast_pipeline(root)
    vintage_summary = build_forecast_vintages(root)
    scenario_summary = run_scenario_pipeline(root)
    monitoring_summary = build_forecast_monitoring(root)
    dashboard_summary = build_dashboard_data(root)
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
        f"Forecast vintages {vintage_summary['append_only_status']}: "
        f"{vintage_summary['vintage_count']} runs, "
        f"{vintage_summary['pending_row_count']} pending rows"
    )
    print(
        f"Scenario analysis: {scenario_summary['scenario_count']} plans across "
        f"{scenario_summary['horizon_days'][-1]} days"
    )
    print(
        f"Forecast monitoring {monitoring_summary['overall_status']}: "
        f"{monitoring_summary['alert_count']} alerts through "
        f"{monitoring_summary['observed_through']}"
    )
    print(
        f"Dashboard ready through {dashboard_summary['forecast_end_date']}: "
        f"{len(dashboard_summary['scenarios'])} scenarios"
    )


if __name__ == "__main__":
    main()
