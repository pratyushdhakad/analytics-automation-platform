import csv
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from shutil import copytree

from analytics_automation_platform.evaluation import (
    evaluate_backtest,
    rolling_origin_backtest,
)
from analytics_automation_platform.forecast_pipeline import run_forecast_pipeline
from analytics_automation_platform.forecasting import (
    build_future_driver_plan,
    feature_vector,
    fit_driver_regression,
    seasonal_naive_forecast,
)
from analytics_automation_platform.history import generate_history
from analytics_automation_platform.ingestion import run_ingestion, sha256_file
from analytics_automation_platform.metrics import build_daily_metrics


ROOT = Path(__file__).resolve().parents[1]
FORECAST_ARTIFACTS = [
    "forecast_backtest.csv",
    "forecast_driver_plan.csv",
    "forecast_evaluation.json",
    "forecast_summary.json",
    "revenue_forecast.csv",
]


def build_test_root(path: Path) -> None:
    copytree(ROOT / "config", path / "config")
    copytree(ROOT / "data", path / "data")
    generate_history(path)
    run_ingestion(path)
    build_daily_metrics(path)


class ForecastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        build_test_root(cls.root)
        with (
            cls.root / "artifacts" / "marts" / "daily_revenue_metrics.csv"
        ).open(newline="", encoding="utf-8") as handle:
            cls.history = list(csv.DictReader(handle))
        with (cls.root / "config" / "forecasting.json").open(
            encoding="utf-8"
        ) as handle:
            cls.config = json.load(handle)
        cls.records, cls.origins = rolling_origin_backtest(cls.history, cls.config)
        cls.evaluation = evaluate_backtest(
            cls.records, cls.history, cls.origins, cls.config
        )

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_feature_contract_is_stable_and_excludes_targets(self):
        row = deepcopy(self.history[-1])
        original = feature_vector(row, len(self.history) - 1)
        row["net_revenue_usd"] = "999999999.99"
        row["shipped_revenue_usd"] = "0.00"
        self.assertEqual(original, feature_vector(row, len(self.history) - 1))
        self.assertEqual(len(original), 16)

    def test_driver_prediction_does_not_read_target_from_prediction_row(self):
        model = fit_driver_regression(
            self.history[:-91],
            "net_revenue_usd",
            self.config["ridge_lambda"],
            self.config["prediction_interval"],
        )
        row = deepcopy(self.history[-1])
        baseline = model.predict(row, len(self.history) - 1, 91)
        row["net_revenue_usd"] = "999999999.99"
        self.assertEqual(baseline, model.predict(row, len(self.history) - 1, 91))

    def test_seasonal_forecast_uses_the_52_week_reference(self):
        origin = self.origins[-1]
        horizon_day = 14
        forecast_index = origin + horizon_day - 1
        point, lower, upper = seasonal_naive_forecast(
            self.history[:origin],
            "net_revenue_usd",
            forecast_index,
            horizon_day,
            self.config["season_length_days"],
            self.config["prediction_interval"],
        )
        expected = float(
            self.history[forecast_index - self.config["season_length_days"]][
                "net_revenue_usd"
            ]
        )
        self.assertEqual(point, expected)
        self.assertLessEqual(lower, point)
        self.assertGreaterEqual(upper, point)

    def test_future_driver_plan_is_explicit_and_target_free(self):
        plan = build_future_driver_plan(
            self.history, self.config["future_horizon_days"]
        )
        self.assertEqual(len(plan), 91)
        self.assertEqual(plan[0]["activity_date"], "2026-08-21")
        self.assertEqual(plan[-1]["activity_date"], "2026-11-19")
        self.assertNotIn("net_revenue_usd", plan[0])
        self.assertNotIn("shipped_revenue_usd", plan[0])
        self.assertTrue(
            all(
                row["driver_plan_method"]
                == "52_week_pattern_with_recent_pacing"
                for row in plan
            )
        )

    def test_backtest_has_six_valid_rolling_origins(self):
        self.assertEqual(len(self.origins), 6)
        self.assertGreaterEqual(self.origins[0], 730)
        self.assertEqual(len(self.records), 2 * 2 * 6 * 91)
        for record in self.records:
            self.assertLess(record["origin_date"], record["forecast_date"])
            self.assertLessEqual(record["lower_bound"], record["forecast"])
            self.assertGreaterEqual(record["upper_bound"], record["forecast"])

    def test_champion_selection_rewards_out_of_sample_accuracy(self):
        self.assertEqual(
            self.evaluation["champions"],
            {
                "net_revenue_usd": "driver_regression",
                "shipped_revenue_usd": "seasonal_naive",
            },
        )
        net_metrics = self.evaluation["metrics"]["net_revenue_usd"]
        shipped_metrics = self.evaluation["metrics"]["shipped_revenue_usd"]
        self.assertLess(
            net_metrics["driver_regression"]["91_days"]["wape_pct"],
            net_metrics["seasonal_naive"]["91_days"]["wape_pct"],
        )
        self.assertLess(
            shipped_metrics["seasonal_naive"]["91_days"]["wape_pct"],
            shipped_metrics["driver_regression"]["91_days"]["wape_pct"],
        )

    def test_forecast_outputs_are_byte_for_byte_reproducible(self):
        run_forecast_pipeline(self.root)
        with tempfile.TemporaryDirectory() as directory:
            second_root = Path(directory)
            build_test_root(second_root)
            run_forecast_pipeline(second_root)
            for filename in FORECAST_ARTIFACTS:
                self.assertEqual(
                    sha256_file(self.root / "artifacts" / filename),
                    sha256_file(second_root / "artifacts" / filename),
                )


if __name__ == "__main__":
    unittest.main()
