import csv
import tempfile
import unittest
from pathlib import Path
from shutil import copytree

from analytics_automation_platform.history import generate_history
from analytics_automation_platform.ingestion import run_ingestion
from analytics_automation_platform.metrics import build_daily_metrics


ROOT = Path(__file__).resolve().parents[1]


class MetricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        copytree(ROOT / "config", cls.root / "config")
        copytree(ROOT / "data", cls.root / "data")
        generate_history(cls.root)
        run_ingestion(cls.root)
        cls.summary = build_daily_metrics(cls.root)
        with (cls.root / "artifacts" / "marts" / "daily_revenue_metrics.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            cls.rows = list(csv.DictReader(handle))

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_metric_mart_has_one_row_per_day(self):
        self.assertEqual(len(self.rows), 1096)
        self.assertEqual(len({row["activity_date"] for row in self.rows}), 1096)

    def test_net_revenue_reconciles(self):
        for row in self.rows:
            self.assertLessEqual(
                abs(
                    float(row["gross_revenue_usd"])
                    - float(row["refunds_usd"])
                    - float(row["net_revenue_usd"])
                ),
                0.02,
            )

    def test_channel_spend_reconciles(self):
        for row in self.rows:
            channels = sum(
                float(row[column])
                for column in [
                    "paid_search_spend_usd",
                    "paid_social_spend_usd",
                    "retargeting_spend_usd",
                    "email_spend_usd",
                ]
            )
            self.assertAlmostEqual(channels, float(row["total_marketing_spend_usd"]), places=2)

    def test_yoy_growth_uses_only_prior_observations(self):
        self.assertTrue(all(row["net_revenue_yoy_pct"] == "" for row in self.rows[:365]))
        self.assertTrue(all(row["net_revenue_yoy_pct"] != "" for row in self.rows[365:]))

    def test_summary_is_decision_ready(self):
        self.assertEqual(self.summary["reconciliation_status"], "PASS")
        self.assertEqual(self.summary["quality_check_count"], 6)
        self.assertGreater(self.summary["latest_28_days"]["net_revenue_usd"], 0)
        self.assertIn("ending_backlog_revenue_usd", self.summary["latest_28_days"])

    def test_bigquery_reference_preserves_governed_definitions(self):
        sql = (ROOT / "sql" / "daily_revenue_metrics.sql").read_text(encoding="utf-8")
        self.assertIn("gross_revenue_usd", sql)
        self.assertIn("refunds_usd", sql)
        self.assertIn("LAG(revenue.net_revenue_usd, 365)", sql)
        self.assertIn("SAFE_DIVIDE", sql)


if __name__ == "__main__":
    unittest.main()
