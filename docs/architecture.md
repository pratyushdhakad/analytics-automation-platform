# Day 1 architecture: trust before transformation

## Decision boundary

The ingestion layer has one job: decide whether each source snapshot is safe to expose to downstream transformations. A passing file is not assumed trustworthy merely because it can be parsed.

The publish gate requires every declared check to pass:

1. the header exactly matches the versioned contract;
2. required values are present and parse as their declared types;
3. domain and numeric bounds hold;
4. primary keys are unique;
5. source timestamps meet the fixture freshness SLA; and
6. cross-source foreign keys resolve.

Only then does the pipeline write the normalized raw layer and evidence manifests.

## Layering

```text
data/source/*.csv
    -> config/sources.json
    -> source-level contract checks
    -> cross-source relationship checks
    -> artifacts/raw/*.csv
    -> ingestion_manifest.json + quality_report.json
```

`ingestion_manifest.json` answers what ran, which inputs were used, how many records moved, and whether downstream publication is allowed. `quality_report.json` preserves the check-level reasoning behind that gate.

## Determinism and lineage

- The fixture uses a declared `fixture_as_of` timestamp rather than the wall clock.
- The run identifier derives from the contract version and fixture timestamp.
- Each input records a SHA-256 content hash.
- JSON keys, indentation, newlines, and CSV line endings are stable.
- The tests execute the pipeline twice in isolated directories and compare every generated file hash.

This makes output drift reviewable in Git and avoids false changes caused by runtime timestamps.

## Production extension

A production implementation would replace local fixtures with connectors for BigQuery, SaaS APIs, and object storage; store contracts in a governed registry; and emit run metadata to an observability warehouse. The same validation boundary can remain, but credentials, raw data, and rejected records would use access-controlled storage rather than Git.

