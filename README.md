# Revenue Forecasting Control Tower

A reliability-first analytics platform for forecasting revenue from seasonality, marketing investment, affiliate activity, sales, and shipment trends.

> Portfolio demonstration using deterministic synthetic data only. No employer, customer, or private operational data is included.

## Business question

What revenue should leadership expect over the next 4, 8, and 13 weeks—and how could marketing plans, affiliate activity, promotions, and fulfillment constraints change the outcome?

The decision owner is a revenue, marketing, or analytics leader who needs an explainable forecast and an auditable publish-or-hold decision before committing budget or operating capacity.

## Day 2 build status

The forecast-ready data foundation currently:

- generates 1,096 days of deterministic synthetic revenue history;
- models annual and weekday seasonality, commercial events, growth, refunds, stockout pressure, and fulfillment backlog;
- captures daily spend for paid search, paid social, retargeting, and email;
- captures partner-level affiliate clicks, orders, revenue, and commissions;
- separates booked net revenue from shipped revenue and backlog release;
- publishes a governed daily metric mart with BigQuery-compatible SQL;
- applies versioned JSON data contracts;
- validates column presence, types, primary keys, accepted values, and numeric bounds;
- checks source freshness against a fixed fixture timestamp;
- verifies cross-source date and refund relationships;
- writes normalized raw-layer outputs only after validation succeeds;
- records SHA-256 lineage, row counts, freshness, and check results in a run manifest;
- reconciles revenue, channel spend, affiliates, and shipment-gap arithmetic; and
- reproduces generated history and outputs byte for byte with automated tests.

## Quick start

```bash
make test
make run
```

Generated outputs are written to `artifacts/`:

- `raw/*.csv` — contract-validated source snapshots;
- `ingestion_manifest.json` — run identity, lineage hashes, row counts, freshness, and publish gate;
- `quality_report.json` — check-level evidence for every source and relationship;
- `marts/daily_revenue_metrics.csv` — 1,096 forecast-ready daily observations;
- `metric_summary.json` — latest 28-day decision metrics; and
- `metric_quality_report.json` — metric reconciliation evidence.

The project uses only the Python standard library, so the deterministic pipeline has no dependency installation step.

## Decision flow

```mermaid
flowchart LR
    A[Revenue and shipment history] --> D[Contract validation]
    B[Channel marketing history] --> D
    C[Affiliate partner history] --> D
    D --> E[Cross-source integrity]
    E --> F[Governed daily metrics]
    F --> G[Reconciliation evidence]
    G --> H{Publish gate}
    H -->|PASS| I[Safe for forecasting]
    H -->|HOLD| J[Quarantine and investigate]
```

## Five-day roadmap

1. **Reliable ingestion:** deterministic fixtures, source registry, data contracts, quality gate — complete
2. **Revenue data foundation:** three-year seasonal history, marketing and affiliate drivers, sales-to-shipment trends, governed metrics — complete
3. **Forecasting engine:** seasonal baselines, external-regressor models, rolling-origin backtests, accuracy and bias
4. **Growth scenarios:** planned channel spend, affiliate, promotion, and fulfillment-capacity scenarios
5. **Decision experience:** executive forecast dashboard, CI, GitHub Pages, profile refresh, interview walkthrough

## Repository map

```text
src/analytics_automation_platform/  history generation, contracts, ingestion, governed metrics, pipeline
config/                             source and metric contracts
data/source/                        deterministic revenue, marketing, affiliate, and Day 1 fixtures
sql/                                BigQuery reference transformation
tests/                              contract, signal, reconciliation, lineage, and reproducibility tests
artifacts/raw/                      validated source snapshots
artifacts/marts/                    forecast-ready daily metric mart
artifacts/                          run, data-quality, metric-quality, and summary evidence
docs/                               architecture and revenue-foundation decisions
```

## AI-augmented build method

I use AI as an engineering multiplier for implementation, edge-case generation, and documentation. I own the business framing, contracts, architecture, evaluation criteria, tests, and every published decision. Generated work is accepted only after it runs, survives tests, and can be explained.

## Current limitations

- Source extracts are deterministic synthetic fixtures rather than live warehouse, advertising, affiliate, or fulfillment systems.
- The fixture timestamp is fixed so the repository remains deterministic; production freshness would use the orchestrator's scheduled timestamp.
- Marketing efficiency and attributed orders are predictive planning signals, not causal incrementality or ROAS claims.
- Synthetic seasonality and driver relationships prove engineering behavior, not real-world forecast accuracy.
- Day 2 creates the feature history; forecasting and rolling-origin evaluation arrive on Day 3.

See [the revenue data foundation](docs/revenue-data-foundation.md) for signal design, governed definitions, modeling boundaries, and the BigQuery extension.

## License

MIT
