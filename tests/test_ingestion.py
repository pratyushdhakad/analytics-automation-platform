import tempfile
import unittest
from pathlib import Path
from shutil import copytree

from analytics_automation_platform.ingestion import build_run_id, run_ingestion, sha256_file


ROOT = Path(__file__).resolve().parents[1]


class IngestionTests(unittest.TestCase):
    def fixture_root(self, target):
        copytree(ROOT / "config", target / "config")
        copytree(ROOT / "data", target / "data")

    def test_pipeline_publishes_pass_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            self.fixture_root(target)
            manifest = run_ingestion(target)
            self.assertEqual(manifest["publish_gate"], "PASS")
            self.assertEqual(manifest["source_count"], 3)
            self.assertEqual(manifest["total_rows"], 23)

    def test_pipeline_writes_all_raw_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            self.fixture_root(target)
            run_ingestion(target)
            outputs = sorted(path.name for path in (target / "artifacts" / "raw").glob("*.csv"))
            self.assertEqual(outputs, ["ad_spend.csv", "orders.csv", "refunds.csv"])

    def test_run_id_is_deterministic(self):
        first = build_run_id("1.0.0", "2026-08-20T12:00:00Z")
        second = build_run_id("1.0.0", "2026-08-20T12:00:00Z")
        self.assertEqual(first, second)

    def test_output_is_byte_for_byte_reproducible(self):
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = Path(first_dir)
            second = Path(second_dir)
            self.fixture_root(first)
            self.fixture_root(second)
            run_ingestion(first)
            run_ingestion(second)
            first_files = sorted(path.relative_to(first) for path in (first / "artifacts").rglob("*") if path.is_file())
            second_files = sorted(path.relative_to(second) for path in (second / "artifacts").rglob("*") if path.is_file())
            self.assertEqual(first_files, second_files)
            for relative in first_files:
                self.assertEqual(sha256_file(first / relative), sha256_file(second / relative))


if __name__ == "__main__":
    unittest.main()

