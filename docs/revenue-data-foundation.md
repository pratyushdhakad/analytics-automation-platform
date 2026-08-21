# Day 2 revenue data foundation

## Planning question

What revenue should leadership expect over the next 4, 8, and 13 weeks, and how could seasonality, marketing plans, affiliate activity, promotions, and fulfillment constraints change that outcome?

Day 2 does not train a forecast. It establishes the historical signal and governed definitions that every forecast must use.

## Synthetic signal design

The deterministic fixture covers 2023-08-21 through 2026-08-20 at daily grain. It contains:

- annual seasonality with a controlled fourth-quarter peak;
- distinct weekday demand and shipping-capacity patterns;
- a gradual underlying growth trend;
- recurring monthly promotions plus summer and holiday events;
- four marketing channels with spend, impressions, clicks, and attributed orders;
- three affiliate partners with clicks, orders, revenue, and commissions;
- refunds modeled with a five-day lag from prior sales;
- sales, units, shipped value, shipped units, stockout pressure, and an explicit fulfillment backlog.

Noise is produced from stable SHA-256 inputs rather than an unseeded random generator. Re-running the history generator therefore produces identical bytes.

## Governed definitions

`config/metrics.json` is the public contract for the decision layer. Three distinctions matter:

1. Net revenue equals gross revenue less refunds.
2. Affiliate revenue is a subset of gross revenue, not additional revenue.
3. Marketing efficiency is a predictive planning ratio, not a causal return-on-ad-spend claim.

The pipeline tests six reconciliation rules before publishing the metric mart. These include daily-grain continuity, revenue arithmetic, channel spend totals, affiliate bounds, shipment-gap arithmetic, and nonnegative operating values.

## Forecast-ready outputs

`artifacts/marts/daily_revenue_metrics.csv` contains one row for each of 1,096 days. Future modeling can use:

- targets: net revenue, gross revenue, orders, units sold, shipped revenue, units shipped;
- seasonal features: weekday, annual position, and named commercial events;
- external regressors: channel spend, affiliate activity, promotions, and stockout rate;
- operating state: ending shipment backlog and the daily revenue-to-shipment gap.

## Modeling boundary

The future forecast may learn predictive relationships between revenue and marketing inputs. That does not establish incremental or causal marketing impact. A production marketing-mix model would require causal controls, spend interventions, lag and saturation assumptions, and fit diagnostics beyond this forecasting pipeline.

## BigQuery extension

`sql/daily_revenue_metrics.sql` expresses the same governed mart in BigQuery Standard SQL. In production, source contracts would gate raw BigQuery tables, the SQL model would build the daily feature table, and scheduled model runs would write forecasts and evaluation evidence to governed datasets.

