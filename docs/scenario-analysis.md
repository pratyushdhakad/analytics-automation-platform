# Growth scenario analysis

Day 4 converts the single Day 3 driver plan into seven comparable 13-week operating scenarios. The purpose is not to claim one precise future. It is to show leadership how forecasted net and shipped revenue move when plans change—and which assumptions create that movement.

## Scenario set

| Scenario | Marketing | Affiliate | Promotion | Fulfillment capacity |
|---|---|---|---|---|
| Base plan | Current plan | Current plan | Current calendar | Current plan |
| Downside | 5–12% lower by channel | 15% lower | 10% lower event intensity | 5% lower |
| Upside | 5–15% higher by channel | 15% higher | 15% higher event intensity | 12% higher |
| Marketing acceleration | 5–20% higher by channel | Held constant | Held constant | Held constant |
| Affiliate expansion | Held constant | 25% higher | Held constant | Held constant |
| Promotion push | Held constant | Held constant | 25% higher event intensity | Held constant |
| Capacity relief | Held constant | Held constant | Held constant | 25% higher |

All values are versioned in `config/scenarios.json`. Isolated scenarios change one lever family at a time, while upside and downside show coordinated operating plans.

## Hybrid scenario method

The Day 3 champion forecast remains the absolute baseline. This matters because the seasonal model beat driver regression for shipped revenue. Replacing that winner with a worse model just to make scenarios responsive would weaken the forecast.

For marketing, affiliate, and promotion changes, the engine:

1. scores the base driver plan with the fitted target model;
2. scores the changed scenario plan with the same model;
3. calculates only the model-implied delta; and
4. adds that delta to the target's champion baseline and interval.

This `champion_baseline_plus_driver_delta` method preserves the best-tested level forecast while using a consistent model for conditional sensitivity.

## Channel, promotion, and capacity treatment

- The future plan now retains paid search, paid social, retargeting, and email amounts, and every scenario reconciles channel spend back to total spend.
- The current driver model uses aggregate marketing spend, so channel multipliers affect revenue through their combined total. Channel-specific response curves are a production extension, not a hidden claim.
- Promotion intensity scales only the model's incremental scheduled-event contribution relative to a no-event counterfactual. It does not create new promotion dates.
- Fulfillment capacity does not change booked net revenue. Extra capacity releases the configured share of a positive forecasted demand-to-shipment gap; reduced capacity scales shipment realization downward.
- The capacity rule is an explainable planning heuristic, not a warehouse network or inventory simulation.

## 13-week comparison

| Scenario | Net revenue | Delta vs base | Shipped revenue | Shipment delta | Marketing spend delta |
|---|---:|---:|---:|---:|---:|
| Upside | $955,855 | +$77,993 | $875,100 | +$70,684 | +$16,094 |
| Marketing acceleration | $943,737 | +$65,875 | $838,015 | +$33,599 | +$20,612 |
| Affiliate expansion | $921,997 | +$44,135 | $844,830 | +$40,414 | $0 |
| Base plan | $877,862 | $0 | $804,416 | $0 | $0 |
| Capacity relief | $877,862 | $0 | $840,240 | +$35,824 | $0 |
| Downside | $808,125 | -$69,738 | $719,717 | -$84,699 | -$13,519 |

The promotion-only result remains in the full ranking artifact. Its relatively small effect is evidence that scheduled event indicators add limited marginal signal after calendar and commercial drivers are controlled; the engine does not inflate that result for presentation.

## Decision interpretation

- **Upside** creates the highest modeled total but depends on coordinated execution across several teams.
- **Marketing acceleration** produces a planning ratio of 3.196 incremental net-revenue dollars per incremental spend dollar. This is a predictive sensitivity, not causal ROAS.
- **Affiliate expansion** has a strong modeled response without added paid-media spend, but assumes partner capacity can deliver 25% more attributed revenue.
- **Capacity relief** changes when revenue ships, not how much demand is booked.
- **Downside** defines the operating risk envelope and highlights a larger shipment impact than booked-revenue impact.

Scenario outputs should guide a conversation about plan feasibility, capacity, and risk. They should not independently authorize spend.

## Produced evidence

- `scenario_forecasts.csv` — 1,274 daily target-scenario forecasts with intervals and assumptions;
- `scenario_ranking.csv` — ranked 13-week decision comparison; and
- `scenario_summary.json` — full 4-, 8-, and 13-week scenario scorecard.
