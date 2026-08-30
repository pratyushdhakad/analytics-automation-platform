# Forecast Monitoring and Response

## Decision

Can the current champion forecasts remain in use, or should an analyst review the model, driver plan, or uncertainty range before the next operating decision?

The monitor turns out-of-sample forecast evidence into one of three states:

- `HEALTHY` — no primary-window thresholds are breached;
- `WATCH` — at least one warning threshold is breached and an analyst review is required; or
- `CRITICAL` — at least one critical threshold is breached and forecast-dependent commitments should pause.

## Evidence boundary

This repository has no live actuals. The monitoring job therefore uses only the latest rolling-origin holdout and each target's selected champion model. The origin is 2026-05-21 and the 91-day observation window ends on 2026-08-20. Every monitored observation was outside the training data available at that origin.

That makes the workflow an honest production-pattern demonstration. The project now retains deterministic immutable vintages and a separate point-in-time observation view. Monitoring still reads the latest rolling holdout directly; a later scheduled-operations increment will make it consume newly observed vintage rows.

## Versioned thresholds

Thresholds live in `config/monitoring.json` and are evaluated on the 91-day primary window.

| Metric | WATCH | CRITICAL | Purpose |
|---|---:|---:|---|
| WAPE | ≥10% | ≥15% | Detect material absolute error |
| Absolute bias | ≥8% | ≥12% | Detect systematic over- or under-prediction |
| 90% interval coverage | <85% | <75% | Detect uncertainty ranges that are too narrow |

All thresholds are portfolio defaults. Production thresholds should reflect decision tolerance, target volatility, forecast horizon, and escalation ownership.

## Current result

| Target | Champion | Status | WAPE | Bias | Coverage |
|---|---|---|---:|---:|---:|
| Net revenue | Driver regression | HEALTHY | 1.53% | +0.67% | 96.70% |
| Shipped revenue | Seasonal naive | WATCH | 8.83% | -8.44% | 95.60% |

Shipment bias is the only breach. A negative bias means the forecast is below actual shipped revenue. The response message points to plan, backlog, and capacity assumptions because those are the most relevant operational inputs—not because the monitor claims causal diagnosis.

## Automated response contract

Each alert contains:

- target and metric;
- severity;
- observed value and breached threshold; and
- a deterministic operator message.

The monitor writes `artifacts/forecast_monitoring.json` for machines and the dashboard, plus `artifacts/forecast_alerts.csv` for routing into a BI table, ticket queue, email workflow, or chat notification.

## Production extension

1. Move the demonstrated CSV vintage contract into a warehouse table with append-only permissions.
2. Replace fixture timestamps with scheduler issue times and warehouse arrival times.
3. Evaluate short and long horizons separately on a scheduled cadence.
4. Route WATCH alerts to an analyst and CRITICAL alerts to the decision owner.
5. Record acknowledgement, diagnosis, corrective action, and resolution time.
6. Recalibrate thresholds only through a reviewed configuration change.

The monitor reports evidence and routing severity. It does not automatically retrain models or override operating plans.
