# Forecasting and evaluation

Day 3 turns the governed daily metric mart into a 13-week forecast with an explicit model-selection decision. The design favors evidence over model complexity: every target keeps the model that performs best in rolling-origin backtests.

## Forecast contract

| Decision | Value |
|---|---|
| As-of date | 2026-08-20 |
| Forecast horizon | 91 days / 13 weeks |
| Decision windows | 28, 56, and 91 days |
| Targets | Net revenue and shipped revenue |
| Seasonal period | 364 days, preserving weekday alignment |
| Evaluation | Six rolling origins, 28 days apart |
| Minimum training history | 730 days |
| Uncertainty | 90% empirical prediction intervals |

The forecasting stage reads only `artifacts/marts/daily_revenue_metrics.csv`. This keeps ingestion, metric governance, modeling, and presentation as separate, testable boundaries.

## Candidate models

### Seasonal naive

The benchmark uses the observation from the same weekday 52 weeks earlier. It is deliberately hard to beat when annual and weekday seasonality dominate. Its interval radius comes from historical absolute 52-week errors and widens with forecast horizon.

### Driver regression

The challenger is a ridge-regularized linear model with:

- trend;
- annual sine and cosine terms;
- weekday indicators;
- total marketing spend;
- affiliate revenue;
- stockout rate; and
- promotion and holiday-event indicators.

The regularization penalty reduces coefficient instability. Target values are excluded from the prediction feature vector, and automated tests prove that changing a target in a scoring row cannot change its prediction.

## Leakage controls

Each rolling origin fits a new model using only observations available through that origin. Forecast dates always fall after the training cutoff. The seasonal benchmark can reference only a date inside the available training history.

For the driver model, backtests use realized drivers as a proxy for the plan that would have been available at the origin. The evaluation artifact labels this `observed_as_planned`. This isolates model fit from plan error, but it will usually look better than a production forecast built on imperfect channel plans. A mature implementation should snapshot original spend, affiliate, promotion, and capacity plans at every forecast run.

## Scorecard

Champion selection uses 91-day WAPE. Other metrics remain visible so a low-error but systematically biased or poorly calibrated model cannot hide behind one score.

| Target | Model | 91-day WAPE | MASE | Bias | 90% interval coverage | Decision |
|---|---:|---:|---:|---:|---:|---|
| Net revenue | Seasonal naive | 9.48% | 0.867 | -9.24% | 96.52% | Benchmark |
| Net revenue | Driver regression | 1.68% | 0.154 | +0.67% | 93.41% | Champion |
| Shipped revenue | Seasonal naive | 9.60% | 0.950 | -9.40% | 93.22% | Champion |
| Shipped revenue | Driver regression | 12.30% | 1.217 | +1.87% | 87.91% | Rejected |

The split decision is intentional. Marketing and affiliate signals explain booked net revenue well in the synthetic history. Shipment timing also depends on backlog release and fulfillment constraints, so the driver model does not beat the simpler seasonal benchmark. The pipeline does not promote complexity when the evidence does not support it.

## Future driver plan

The 91-day forecast is conditional on an explicit plan. Marketing spend and affiliate revenue combine the same-weekday 52-week pattern with the latest 28-day pacing, capped to a reasonable range. Stockout pressure uses the 52-week reference, while commercial events follow the deterministic calendar.

These inputs answer “what revenue is consistent with this operating plan?” They do not estimate causal lift or incremental ROAS. Day 4 will make the assumptions adjustable through scenarios.

## Metrics

- **WAPE:** absolute error divided by total absolute actual revenue; used for champion selection.
- **MASE:** mean absolute error divided by the in-sample 52-week seasonal-naive error; values below 1 beat that scale benchmark.
- **Bias:** signed total error divided by total absolute actual revenue; positive means over-forecasting.
- **Coverage:** share of actual observations inside the stated prediction interval.
- **RMSE:** emphasizes larger misses more than MAE.

The period summaries add daily marginal lower and upper bounds. Those sums are useful planning envelopes but are not statistically valid joint-period intervals because cross-day error dependence is not modeled.

## Produced evidence

- `forecast_backtest.csv` — observation-level out-of-sample predictions and errors;
- `forecast_evaluation.json` — comparable model scorecards and champions;
- `forecast_driver_plan.csv` — explicit future planning assumptions;
- `revenue_forecast.csv` — daily champion forecasts and intervals; and
- `forecast_summary.json` — 4-, 8-, and 13-week executive totals.
