# Interview walkthrough

## 30-second version

I built a revenue forecasting control tower that separates data trust, forecast accuracy, scenario sensitivity, monitoring, and executive communication. It creates three years of deterministic synthetic sales, marketing, affiliate, and shipment history; validates six source contracts; compares seasonal and driver-aware models across six rolling origins; keeps a different champion for booked and shipped revenue; monitors the latest holdout for error, bias, and interval coverage; and turns seven operating plans into an interactive 13-week dashboard. The entire project is standard-library Python, tested, reproducible, and deployed through CI and GitHub Pages.

## Three-minute walkthrough

### 1. Start with the decision

Leadership needs to know what net and shipped revenue to expect over 4, 8, and 13 weeks, how much downside exists, and which operating levers could change the result. I treated “can we trust the forecast?” as a product requirement rather than a footnote.

### 2. Establish the data boundary

The pipeline validates six deterministic source datasets and publishes downstream data only when schema, primary-key, accepted-value, freshness, and relationship checks pass. The governed mart keeps affiliate revenue as a subset of sales and separates booked net revenue from shipment realization and backlog release.

### 3. Let evaluation choose the model

I compared a same-weekday 52-week baseline with a ridge-regularized driver model across six rolling origins. Driver regression won for net revenue at 1.68% 13-week WAPE. Seasonal naive won for shipped revenue at 9.60%. I kept both champions because complexity should earn promotion independently for each target.

### 4. Turn forecasts into decisions

The base plan forecasts about $877.9K of 13-week net revenue. Seven versioned scenarios create a range from about $808.1K downside to $955.9K upside. The shipment view separately shows that capacity relief can release about $35.8K without changing booked demand.

### 5. Close the feedback loop

The monitor evaluates the latest champion holdout against versioned WAPE, bias, and interval-coverage thresholds. Net revenue is HEALTHY. Shipped revenue is WATCH because it under-predicts actuals by 8.44%, so the alert routes an analyst to review plan, backlog, and capacity assumptions before the next refresh.

### 6. Explain the guardrails

Marketing and affiliate inputs are predictive signals, not causal ROAS. Scenario forecasts preserve the champion baseline and add only a fitted driver-model delta. Capacity uses an explicit shipment-gap heuristic rather than pretending the project contains a warehouse simulation. Those limitations are visible in the dashboard and documentation.

### 7. Close on engineering quality

The project runs without third-party Python dependencies, has a deterministic test suite, rebuilds all evidence in CI, and fails when committed artifacts are stale. GitHub Pages deploys the same static dashboard data contract produced by the tested pipeline.

## Questions I expect

### Why use synthetic data?

It lets me publish the full engineering and evaluation pattern without exposing employer or customer information. Deterministic fixtures also make every output byte-for-byte reproducible.

### Why did different targets choose different models?

Booked demand responds directly to the modeled calendar, marketing, affiliate, and stockout signals. Shipment timing also depends on backlog and capacity dynamics. In rolling-origin evaluation, the driver model improved net revenue but did not beat the seasonal benchmark for shipments, so I did not force one architecture across both decisions.

### Is the marketing scenario causal?

No. It answers what forecast is consistent with a changed plan under learned historical relationships. A causal budget recommendation would require an experiment, quasi-experimental design, or incrementality model plus point-in-time plan data.

### How would you productionize it?

I would replace CSV extracts with partitioned warehouse models, snapshot original plans at each forecast origin, and persist immutable forecast vintages. The existing monitor would join each vintage to newly landed actuals, route WATCH and CRITICAL alerts through the orchestrator, and record acknowledgement and resolution. I would also add model-registry approval states, recalibrate intervals on held-out residuals, and publish the dashboard behind governed access.

### What did AI do?

I used AI as an implementation and review multiplier: exploring architecture, generating edge cases, accelerating documentation, and tightening tests. I owned the business framing, modeling boundaries, evaluation criteria, published claims, and the decision to reject misleading interpretations such as treating a confounded stockout coefficient as a causal capacity effect.

## Repository tour

1. Start in `README.md` for the business decision and scorecards.
2. Run `make test` and `make run`.
3. Open `config/forecasting.json`, `config/scenarios.json`, and `config/monitoring.json` to show explicit contracts.
4. Show `artifacts/forecast_evaluation.json` for model-selection evidence.
5. Show `artifacts/scenario_ranking.csv` for the operating decision.
6. Show `artifacts/forecast_monitoring.json` and the automated WATCH alert.
7. Open the live dashboard, switch between net and shipped revenue, and review the monitoring panel.
8. Finish with `.github/workflows/ci.yml` to show reproducibility is enforced.
