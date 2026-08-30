# Immutable Forecast Vintages

## Decision

A forecast changes over time. Leadership needs to know not only the newest number, but also exactly what was predicted, by which model, and with which information at every earlier issue date.

This increment answers:

> Can an analyst reproduce a historical forecast without replacing it with today's updated answer or accidentally joining an actual that was not yet available?

## Success contract

The implementation is accepted only when:

1. all six historical forecast origins and the current forecast remain separately queryable;
2. every row has a stable vintage ID, origin date, issue timestamp, forecast version, model, and model version;
3. publishing the same bytes again succeeds, while changing an existing vintage identity fails;
4. an actual appears in the evaluation view only after its configured availability timestamp;
5. all current future forecasts remain `PENDING`; and
6. every generated file is byte-for-byte reproducible.

## Plain-English example

Suppose a forecast was issued at the end of January 1 for January 2.

- The forecast is saved under the January 1 vintage.
- The January 2 actual is configured to become available on January 3 at 06:00 UTC.
- A report evaluated before that timestamp must show the actual as blank and the status as `PENDING`.
- A report evaluated afterward may show the actual and calculate the forecast error.
- If someone later tries to change the saved January 1 forecast while keeping the same vintage ID, the pipeline stops.

This is point-in-time correctness: the system respects what was knowable at the time rather than using information from the future.

## Contract

`config/vintages.json` controls:

- `vintage_contract_version` — version of the governance rules;
- `issue_time_utc` — deterministic issue time applied to each origin;
- `actual_availability_lag_days` — delay between the activity date and availability;
- `actual_availability_time_utc` — time the delayed actual becomes usable;
- `evaluation_as_of_utc` — simulated time for the current evaluation view; and
- `model_versions` — explicit version for every candidate model.

The timestamps are deterministic portfolio fixtures. A production system would receive issue and ingestion timestamps from its orchestrator and warehouse.

## Pipeline

```text
Champion backtest rows ─┐
                       ├─> stable vintage identities ─> append-only forecast file
Current future forecast ┘                                   │
                                                            ├─> manifest and lineage
Governed actual history ─> availability timestamps ─> as-of join
                                                            │
                                                            └─> observed/pending view
```

The historical vintages retain only the selected model for each target at each origin. The current vintage retains the 91-day future forecast for both targets.

## Published evidence

### `artifacts/forecast_vintages.csv`

The append-only forecast record. Its primary identity is:

```text
vintage_id + target + forecast_date
```

The initial fixture contains:

- 7 distinct vintages;
- 1,092 selected historical predictions; and
- 182 current future predictions.

### `artifacts/forecast_vintage_observations.csv`

A point-in-time evaluation view. It contains the vintage metadata plus:

- the actual-availability timestamp;
- actual value, when legally available;
- error calculated as forecast minus actual;
- `OBSERVED` or `PENDING`; and
- the evaluation as-of timestamp.

At the configured as-of timestamp, all 1,092 historical predictions are observed and all 182 current future predictions remain pending.

### `artifacts/forecast_vintage_manifest.json`

The compact audit result. It records counts, origin dates, the current vintage ID, append-only and point-in-time PASS decisions, and SHA-256 hashes for every upstream input.

## Append-only behavior

`publish_append_only` supports two safe actions:

- re-publish an existing identity with identical content; or
- append a previously unseen identity.

It rejects a third action: changing content already stored under an existing identity. A legitimate model change therefore needs a new model or forecast version, producing a new identity instead of rewriting history.

The CSV implementation demonstrates the contract locally. Production would enforce the same rule with warehouse permissions, an append-only table, object versioning, or event storage.

## Leakage controls

The pipeline blocks or avoids four failure modes:

1. a forecast date on or before its origin date;
2. a forecast issued after its actual was already available;
3. an actual joined before the configured availability timestamp; and
4. a missing explicit model version.

Automated tests also inject a fake future actual worth `$999,999.99`. The value remains blank because its availability timestamp is later than the evaluation time.

## Run it

```bash
make vintages
```

The complete build still runs with:

```bash
make test
make run
```

## What this proves—and what it does not

This proves append-only identity checks, deterministic timestamps, point-in-time joining, lineage, pending-future behavior, and reproducibility against synthetic fixtures.

It does not claim that a CSV file is a multi-user production database. A production extension would add:

- warehouse-native append-only permissions;
- real ingestion and issue timestamps;
- scheduler run IDs and service identities;
- late-arriving actual revision policies;
- partitioning by origin and forecast date;
- retention and deletion policies; and
- an approval record for model promotion.

The next apprenticeship increment is the champion/challenger registry, which will give model candidates governed lifecycle states and a human approval record.
