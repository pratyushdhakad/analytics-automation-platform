import csv
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from shutil import copytree

from analytics_automation_platform.forecast_pipeline import run_forecast_pipeline
from analytics_automation_platform.forecasting import CHANNEL_COLUMNS
from analytics_automation_platform.history import generate_history
from analytics_automation_platform.ingestion import run_ingestion, sha256_file
from analytics_automation_platform.metrics import build_daily_metrics
from analytics_automation_platform.scenario_pipeline import run_scenario_pipeline
from analytics_automation_platform.scenarios import (
    scenario_driver_row,
    validate_scenario_config,
)


ROOT = Path(__file__).resolve().parents[1]
SCENARIO_ARTIFACTS = [
    "scenario_forecasts.csv",
    "scenario_ranking.csv",
    "scenario_summary.json",
]


def build_scenario_root(path: Path) -> None:
    copytree(ROOT / "config", path / "config")
    copytree(ROOT / "data", path / "data")
    generate_history(path)
    run_ingestion(path)
    build_daily_metrics(path)
    run_forecast_pipeline(path)
    run_scenario_pipeline(path)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class ScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        build_scenario_root(cls.root)
        cls.plan = read_csv(cls.root / "artifacts" / "forecast_driver_plan.csv")
        cls.forecast = read_csv(cls.root / "artifacts" / "revenue_forecast.csv")
        cls.rows = read_csv(cls.root / "artifacts" / "scenario_forecasts.csv")
        with (cls.root / "artifacts" / "scenario_summary.json").open(
            encoding="utf-8"
        ) as handle:
            cls.summary = json.load(handle)
        with (cls.root / "config" / "scenarios.json").open(
            encoding="utf-8"
        ) as handle:
            cls.config = json.load(handle)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_seven_scenarios_cover_two_targets_and_91_days(self):
        self.assertEqual(self.summary["scenario_count"], 7)
        self.assertEqual(len(self.rows), 7 * 2 * 91)
        self.assertEqual(
            {row["scenario_id"] for row in self.rows},
            {scenario["scenario_id"] for scenario in self.config["scenarios"]},
        )

    def test_scenario_contract_rejects_duplicate_identifiers(self):
        invalid = deepcopy(self.config)
        invalid["scenarios"][1]["scenario_id"] = "base_plan"
        with self.assertRaisesRegex(ValueError, "unique"):
            validate_scenario_config(invalid)

    def test_scenario_contract_rejects_incomplete_channel_plan(self):
        invalid = deepcopy(self.config)
        del invalid["scenarios"][0]["channel_spend_multipliers"]["email"]
        with self.assertRaisesRegex(ValueError, "every channel"):
            validate_scenario_config(invalid)

    def test_base_scenario_preserves_champion_forecast(self):
        base = {
            (row["target"], row["horizon_day"]): row
            for row in self.rows
            if row["scenario_id"] == "base_plan"
        }
        for forecast in self.forecast:
            row = base[(forecast["target"], forecast["horizon_day"])]
            self.assertEqual(row["forecast"], forecast["forecast"])
            self.assertEqual(float(row["delta_vs_base_usd"]), 0.0)

    def test_channel_scenarios_reconcile_to_total_spend(self):
        for scenario in self.config["scenarios"]:
            row = scenario_driver_row(self.plan[0], scenario)
            self.assertAlmostEqual(
                sum(float(row[column]) for column in CHANNEL_COLUMNS),
                float(row["total_marketing_spend_usd"]),
                places=2,
            )

    def test_upside_and_downside_bracket_the_base(self):
        scenarios = self.summary["scenarios"]
        base = scenarios["base_plan"]["horizons"]["91_days"]
        upside = scenarios["upside"]["horizons"]["91_days"]
        downside = scenarios["downside"]["horizons"]["91_days"]
        self.assertGreater(upside["net_revenue_usd"], base["net_revenue_usd"])
        self.assertGreater(
            upside["shipped_revenue_usd"], base["shipped_revenue_usd"]
        )
        self.assertLess(downside["net_revenue_usd"], base["net_revenue_usd"])
        self.assertLess(
            downside["shipped_revenue_usd"], base["shipped_revenue_usd"]
        )

    def test_capacity_relief_changes_shipments_not_booked_revenue(self):
        capacity = self.summary["scenarios"]["capacity_relief"]["horizons"][
            "91_days"
        ]
        self.assertEqual(capacity["net_revenue_delta_vs_base_usd"], 0.0)
        self.assertGreater(capacity["shipped_revenue_delta_vs_base_usd"], 0.0)

    def test_isolated_scenarios_hold_other_levers_constant(self):
        by_id = {
            scenario["scenario_id"]: scenario
            for scenario in self.config["scenarios"]
        }
        self.assertEqual(by_id["affiliate_expansion"]["promotion_multiplier"], 1.0)
        self.assertEqual(
            by_id["affiliate_expansion"]["fulfillment_capacity_multiplier"],
            1.0,
        )
        self.assertTrue(
            all(
                multiplier == 1.0
                for multiplier in by_id["capacity_relief"][
                    "channel_spend_multipliers"
                ].values()
            )
        )

    def test_scenario_outputs_are_byte_for_byte_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            second_root = Path(directory)
            build_scenario_root(second_root)
            for filename in SCENARIO_ARTIFACTS:
                self.assertEqual(
                    sha256_file(self.root / "artifacts" / filename),
                    sha256_file(second_root / "artifacts" / filename),
                )


if __name__ == "__main__":
    unittest.main()
