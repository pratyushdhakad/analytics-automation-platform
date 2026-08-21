import csv
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

from analytics_automation_platform.history import generate_history
from analytics_automation_platform.ingestion import sha256_file


class HistoryTests(unittest.TestCase):
    def rows(self, path):
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def test_generator_is_byte_for_byte_reproducible(self):
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = Path(first_dir)
            second = Path(second_dir)
            generate_history(first)
            generate_history(second)
            for filename in ["revenue_daily.csv", "marketing_daily.csv", "affiliates_daily.csv"]:
                self.assertEqual(
                    sha256_file(first / "data" / "source" / filename),
                    sha256_file(second / "data" / "source" / filename),
                )

    def test_history_covers_three_continuous_years(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            summary = generate_history(root)
            rows = self.rows(root / "data" / "source" / "revenue_daily.csv")
            self.assertEqual(summary["day_count"], 1096)
            self.assertEqual(rows[0]["activity_date"], "2023-08-21")
            self.assertEqual(rows[-1]["activity_date"], "2026-08-20")

    def test_marketing_and_affiliate_grains_are_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            summary = generate_history(root)
            self.assertEqual(summary["marketing_row_count"], 1096 * 4)
            self.assertEqual(summary["affiliate_row_count"], 1096 * 3)

    def test_seasonal_and_event_signals_are_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generate_history(root)
            rows = self.rows(root / "data" / "source" / "revenue_daily.csv")
            by_event = defaultdict(list)
            by_quarter = defaultdict(list)
            for row in rows:
                revenue = float(row["gross_revenue_usd"])
                by_event[row["event_name"]].append(revenue)
                month = int(row["activity_date"][5:7])
                by_quarter[(month - 1) // 3 + 1].append(revenue)
            self.assertGreater(
                sum(by_event["holiday_peak"]) / len(by_event["holiday_peak"]),
                sum(by_event["none"]) / len(by_event["none"]),
            )
            self.assertGreater(
                sum(by_quarter[4]) / len(by_quarter[4]),
                sum(by_quarter[1]) / len(by_quarter[1]),
            )

    def test_shipment_constraints_create_auditable_backlog(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generate_history(root)
            rows = self.rows(root / "data" / "source" / "revenue_daily.csv")
            backlogs = [float(row["ending_backlog_revenue_usd"]) for row in rows]
            self.assertGreater(max(backlogs), 0)
            self.assertTrue(any(value == 0 for value in backlogs))


if __name__ == "__main__":
    unittest.main()

