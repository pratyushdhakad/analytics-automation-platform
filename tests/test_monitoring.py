import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from shutil import copytree

from analytics_automation_platform.forecast_pipeline import run_forecast_pipeline
from analytics_automation_platform.history import generate_history
from analytics_automation_platform.ingestion import run_ingestion, sha256_file
from analytics_automation_platform.metrics import build_daily_metrics
from analytics_automation_platform.monitoring import (
    build_forecast_monitoring,
    validate_monitoring_config,
)


ROOT = Path(__file__).resolve().parents[1]


def build_monitoring_root(path: Path) -> dict:
    copytree(ROOT / "config", path / "config")
    copytree(ROOT / "data", path / "data")
    generate_history(path)
    run_ingestion(path)
    build_daily_metrics(path)
    run_forecast_pipeline(path)
    return build_forecast_monitoring(path)


class MonitoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        cls.monitoring = build_monitoring_root(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_latest_origin_champion_evidence_is_monitored(self):
        self.assertEqual(self.monitoring["origin_date"], "2026-05-21")
        self.assertEqual(self.monitoring["observed_through"], "2026-08-20")
        self.assertEqual(
            self.monitoring["targets"]["net_revenue_usd"]["champion"],
            "driver_regression",
        )
        self.assertEqual(
            self.monitoring["targets"]["shipped_revenue_usd"]["champion"],
            "seasonal_naive",
        )

    def test_monitor_detects_systematic_shipment_underforecast(self):
        shipped = self.monitoring["targets"]["shipped_revenue_usd"]
        self.assertEqual(self.monitoring["overall_status"], "WATCH")
        self.assertEqual(shipped["status"], "WATCH")
        self.assertEqual(shipped["windows"]["91_days"]["bias_pct"], -8.44)
        self.assertEqual(self.monitoring["alert_count"], 1)
        self.assertEqual(self.monitoring["alerts"][0]["metric"], "absolute_bias_pct")
        self.assertIn("under-predicting", self.monitoring["alerts"][0]["message"])

    def test_net_revenue_monitor_remains_healthy(self):
        net = self.monitoring["targets"]["net_revenue_usd"]
        self.assertEqual(net["status"], "HEALTHY")
        self.assertEqual(net["windows"]["91_days"]["wape_pct"], 1.53)
        self.assertEqual(net["windows"]["91_days"]["interval_coverage_pct"], 96.7)

    def test_threshold_contract_rejects_invalid_order(self):
        config = json.loads((ROOT / "config" / "monitoring.json").read_text(encoding="utf-8"))
        invalid = deepcopy(config)
        invalid["thresholds"]["wape_pct"] = {"watch": 15, "critical": 10}
        with self.assertRaisesRegex(ValueError, "WAPE thresholds"):
            validate_monitoring_config(invalid)

    def test_monitoring_outputs_are_byte_for_byte_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            second_root = Path(directory)
            build_monitoring_root(second_root)
            for name in ("forecast_monitoring.json", "forecast_alerts.csv"):
                self.assertEqual(
                    sha256_file(self.root / "artifacts" / name),
                    sha256_file(second_root / "artifacts" / name),
                )


if __name__ == "__main__":
    unittest.main()
