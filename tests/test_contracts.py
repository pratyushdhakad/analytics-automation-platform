import copy
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from analytics_automation_platform.contracts import (
    load_registry,
    load_rows,
    validate_foreign_keys,
    validate_source,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = load_registry(ROOT / "config" / "sources.json")
AS_OF = datetime(2026, 8, 20, 12, tzinfo=timezone.utc)


class ContractTests(unittest.TestCase):
    def source(self, name):
        return next(source for source in REGISTRY["sources"] if source["name"] == name)

    def test_committed_sources_satisfy_contracts(self):
        for source in REGISTRY["sources"]:
            headers, rows = load_rows(ROOT / source["path"])
            checks = validate_source(source, headers, rows, AS_OF)
            self.assertTrue(all(check.status == "PASS" for check in checks))

    def test_missing_column_fails_schema(self):
        source = self.source("orders")
        headers, rows = load_rows(ROOT / source["path"])
        checks = validate_source(source, headers[:-1], rows, AS_OF)
        schema = next(check for check in checks if check.check == "schema")
        self.assertEqual(schema.status, "FAIL")

    def test_duplicate_primary_key_fails(self):
        source = self.source("orders")
        headers, rows = load_rows(ROOT / source["path"])
        checks = validate_source(source, headers, rows + [copy.deepcopy(rows[0])], AS_OF)
        primary_key = next(check for check in checks if check.check == "primary_key")
        self.assertEqual(primary_key.status, "FAIL")

    def test_invalid_domain_value_fails(self):
        source = self.source("orders")
        headers, rows = load_rows(ROOT / source["path"])
        rows[0]["status"] = "pending"
        checks = validate_source(source, headers, rows, AS_OF)
        values = next(check for check in checks if check.check == "values")
        self.assertEqual(values.status, "FAIL")

    def test_negative_numeric_value_fails(self):
        source = self.source("ad_spend")
        headers, rows = load_rows(ROOT / source["path"])
        rows[0]["spend_usd"] = "-1.00"
        checks = validate_source(source, headers, rows, AS_OF)
        values = next(check for check in checks if check.check == "values")
        self.assertEqual(values.status, "FAIL")

    def test_stale_source_fails_freshness(self):
        source = self.source("orders")
        headers, rows = load_rows(ROOT / source["path"])
        for row in rows:
            row["updated_at"] = "2026-08-18T08:00:00Z"
        checks = validate_source(source, headers, rows, AS_OF)
        freshness = next(check for check in checks if check.check == "freshness")
        self.assertEqual(freshness.status, "FAIL")

    def test_refunds_resolve_to_orders(self):
        datasets = {}
        for source in REGISTRY["sources"]:
            _, datasets[source["name"]] = load_rows(ROOT / source["path"])
        checks = validate_foreign_keys(REGISTRY, datasets)
        self.assertEqual(len(checks), 3)
        self.assertTrue(all(check.status == "PASS" for check in checks))

    def test_orphan_refund_fails_relationship(self):
        datasets = {}
        for source in REGISTRY["sources"]:
            _, datasets[source["name"]] = load_rows(ROOT / source["path"])
        datasets["refunds"][0]["order_id"] = "ORD-MISSING"
        checks = validate_foreign_keys(REGISTRY, datasets)
        self.assertEqual(checks[0].status, "FAIL")

    def test_registry_is_valid_json(self):
        payload = json.loads((ROOT / "config" / "sources.json").read_text())
        self.assertEqual(payload["contract_version"], "2.0.0")


if __name__ == "__main__":
    unittest.main()
