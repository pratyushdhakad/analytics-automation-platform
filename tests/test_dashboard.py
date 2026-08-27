import json
import tempfile
import unittest
from pathlib import Path
from shutil import copytree

from analytics_automation_platform.dashboard import build_dashboard_data
from analytics_automation_platform.forecast_pipeline import run_forecast_pipeline
from analytics_automation_platform.history import generate_history
from analytics_automation_platform.ingestion import run_ingestion, sha256_file
from analytics_automation_platform.metrics import build_daily_metrics
from analytics_automation_platform.monitoring import build_forecast_monitoring
from analytics_automation_platform.scenario_pipeline import run_scenario_pipeline


ROOT = Path(__file__).resolve().parents[1]


def build_dashboard_root(path: Path) -> dict:
    copytree(ROOT / "config", path / "config")
    copytree(ROOT / "data", path / "data")
    generate_history(path)
    run_ingestion(path)
    build_daily_metrics(path)
    run_forecast_pipeline(path)
    run_scenario_pipeline(path)
    build_forecast_monitoring(path)
    return build_dashboard_data(path)


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        cls.dashboard = build_dashboard_root(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_dashboard_contract_is_decision_ready(self):
        self.assertEqual(self.dashboard["quality"]["data_gate"], "PASS")
        self.assertEqual(self.dashboard["quality"]["source_count"], 6)
        self.assertEqual(self.dashboard["quality"]["forecast_ready_days"], 1096)
        self.assertEqual(len(self.dashboard["scenarios"]), 7)
        self.assertEqual(self.dashboard["forecast_end_date"], "2026-11-19")

    def test_featured_daily_series_are_complete(self):
        self.assertEqual(set(self.dashboard["daily"]), {"base_plan", "upside", "downside"})
        for scenario in self.dashboard["daily"].values():
            for target_rows in scenario.values():
                self.assertEqual(len(target_rows), 91)
                self.assertEqual(target_rows[0]["day"], 1)
                self.assertEqual(target_rows[-1]["day"], 91)

    def test_dashboard_exposes_champion_evidence(self):
        self.assertEqual(
            self.dashboard["model_health"]["net_revenue_usd"]["champion"],
            "driver_regression",
        )
        self.assertEqual(
            self.dashboard["model_health"]["shipped_revenue_usd"]["champion"],
            "seasonal_naive",
        )

    def test_dashboard_exposes_monitoring_evidence(self):
        self.assertEqual(self.dashboard["monitoring"]["overall_status"], "WATCH")
        self.assertEqual(self.dashboard["monitoring"]["alert_count"], 1)

    def test_dashboard_data_contains_no_private_identifiers(self):
        payload = json.dumps(self.dashboard).lower()
        for prohibited in ("truly free", "@gmail", "@yahoo", "linkedin.com/in"):
            self.assertNotIn(prohibited, payload)

    def test_static_page_has_accessible_controls_and_local_assets(self):
        html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
        self.assertIn('aria-label="Dashboard controls"', html)
        self.assertIn('role="img"', html)
        self.assertIn('href="styles.css"', html)
        self.assertIn('src="app.js"', html)
        self.assertNotIn('src="http', html)
        self.assertNotIn('href="https://fonts.', html)

    def test_static_page_surfaces_monitoring_and_alerts(self):
        html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
        javascript = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="monitoring"', html)
        self.assertIn('aria-labelledby="alert-heading"', html)
        self.assertIn("renderMonitoring", javascript)
        self.assertIn("monitor.alerts", javascript)

    def test_dashboard_output_is_byte_for_byte_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            second_root = Path(directory)
            build_dashboard_root(second_root)
            self.assertEqual(
                sha256_file(self.root / "site" / "data" / "dashboard.json"),
                sha256_file(second_root / "site" / "data" / "dashboard.json"),
            )


if __name__ == "__main__":
    unittest.main()
