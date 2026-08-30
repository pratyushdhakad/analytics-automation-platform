import csv
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
from analytics_automation_platform.vintages import (
    VINTAGE_FIELDS,
    build_forecast_vintages,
    join_vintages_as_of,
    publish_append_only,
    validate_vintage_config,
)


ROOT = Path(__file__).resolve().parents[1]
VINTAGE_ARTIFACTS = [
    "forecast_vintages.csv",
    "forecast_vintage_observations.csv",
    "forecast_vintage_manifest.json",
]


def build_vintage_root(path: Path) -> dict:
    copytree(ROOT / "config", path / "config")
    copytree(ROOT / "data", path / "data")
    generate_history(path)
    run_ingestion(path)
    build_daily_metrics(path)
    run_forecast_pipeline(path)
    return build_forecast_vintages(path)


class VintageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        cls.manifest = build_vintage_root(cls.root)
        with (cls.root / "artifacts" / "forecast_vintages.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            cls.vintages = list(csv.DictReader(handle))
        with (cls.root / "artifacts" / "forecast_vintage_observations.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            cls.observations = list(csv.DictReader(handle))

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_vintage_identity_and_point_in_time_counts(self):
        self.assertEqual(self.manifest["vintage_count"], 7)
        self.assertEqual(self.manifest["forecast_row_count"], 1274)
        self.assertEqual(self.manifest["observed_row_count"], 1092)
        self.assertEqual(self.manifest["pending_row_count"], 182)
        self.assertEqual(
            self.manifest["current_vintage_id"], "vintage-20260820-f1_0_0"
        )
        self.assertEqual(len(self.vintages), 1274)
        self.assertTrue(
            all(row["issued_at_utc"].endswith("Z") for row in self.vintages)
        )
        self.assertTrue(all(row["model_version"] == "1.0.0" for row in self.vintages))

    def test_current_future_actuals_remain_pending(self):
        current = [
            row
            for row in self.observations
            if row["vintage_id"] == self.manifest["current_vintage_id"]
        ]
        self.assertEqual(len(current), 182)
        self.assertTrue(all(row["observation_status"] == "PENDING" for row in current))
        self.assertTrue(all(row["actual"] == "" for row in current))

    def test_as_of_join_blocks_an_actual_until_it_is_available(self):
        vintage = deepcopy(self.vintages[-1])
        actual = {
            "forecast_date": vintage["forecast_date"],
            "target": vintage["target"],
            "actual": "999999.99",
            "actual_available_at_utc": "2026-11-21T06:00:00Z",
        }
        joined = join_vintages_as_of(
            [vintage], [actual], "2026-08-21T06:00:00Z"
        )
        self.assertEqual(joined[0]["observation_status"], "PENDING")
        self.assertEqual(joined[0]["actual"], "")

    def test_append_only_contract_rejects_a_rewritten_identity(self):
        row = {field: "value" for field in VINTAGE_FIELDS}
        row.update(
            {
                "vintage_id": "vintage-1",
                "target": "net_revenue_usd",
                "forecast_date": "2026-01-02",
                "issued_at_utc": "2026-01-01T23:59:59Z",
                "forecast": "100.00",
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "forecast_vintages.csv"
            publish_append_only(path, [row])
            rewritten = deepcopy(row)
            rewritten["forecast"] = "101.00"
            with self.assertRaisesRegex(
                ValueError, "immutable forecast vintage conflict"
            ):
                publish_append_only(path, [rewritten])

    def test_contract_requires_every_model_version(self):
        vintage_config = json.loads(
            (ROOT / "config" / "vintages.json").read_text(encoding="utf-8")
        )
        forecast_config = json.loads(
            (ROOT / "config" / "forecasting.json").read_text(encoding="utf-8")
        )
        del vintage_config["model_versions"]["seasonal_naive"]
        with self.assertRaisesRegex(ValueError, "model_versions missing"):
            validate_vintage_config(vintage_config, forecast_config)

    def test_vintage_outputs_are_byte_for_byte_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            second_root = Path(directory)
            build_vintage_root(second_root)
            for filename in VINTAGE_ARTIFACTS:
                self.assertEqual(
                    sha256_file(self.root / "artifacts" / filename),
                    sha256_file(second_root / "artifacts" / filename),
                )


if __name__ == "__main__":
    unittest.main()
