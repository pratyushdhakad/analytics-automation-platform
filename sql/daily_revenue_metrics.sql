-- BigQuery reference model for the governed daily revenue mart.
-- Affiliate revenue is a subset of gross revenue and must not be added to it.

WITH marketing AS (
  SELECT
    activity_date,
    SUM(spend_usd) AS total_marketing_spend_usd,
    SUM(IF(channel = 'paid_search', spend_usd, 0)) AS paid_search_spend_usd,
    SUM(IF(channel = 'paid_social', spend_usd, 0)) AS paid_social_spend_usd,
    SUM(IF(channel = 'retargeting', spend_usd, 0)) AS retargeting_spend_usd,
    SUM(IF(channel = 'email', spend_usd, 0)) AS email_spend_usd,
    SUM(attributed_orders) AS marketing_attributed_orders
  FROM `raw.marketing_daily`
  GROUP BY activity_date
),

affiliates AS (
  SELECT
    activity_date,
    SUM(revenue_usd) AS affiliate_revenue_usd,
    SUM(commission_usd) AS affiliate_commission_usd,
    SUM(orders) AS affiliate_orders
  FROM `raw.affiliates_daily`
  GROUP BY activity_date
)

SELECT
  revenue.activity_date,
  revenue.gross_revenue_usd,
  revenue.refunds_usd,
  revenue.net_revenue_usd,
  revenue.shipped_revenue_usd,
  revenue.net_revenue_usd - revenue.shipped_revenue_usd AS revenue_to_ship_gap_usd,
  revenue.ending_backlog_revenue_usd,
  revenue.orders,
  revenue.units_sold,
  revenue.units_shipped,
  SAFE_DIVIDE(revenue.gross_revenue_usd, revenue.orders) AS average_order_value_usd,
  marketing.total_marketing_spend_usd,
  marketing.paid_search_spend_usd,
  marketing.paid_social_spend_usd,
  marketing.retargeting_spend_usd,
  marketing.email_spend_usd,
  SAFE_DIVIDE(revenue.gross_revenue_usd, marketing.total_marketing_spend_usd)
    AS marketing_efficiency_ratio,
  marketing.marketing_attributed_orders,
  affiliates.affiliate_revenue_usd,
  affiliates.affiliate_commission_usd,
  affiliates.affiliate_orders,
  SAFE_DIVIDE(affiliates.affiliate_revenue_usd, revenue.gross_revenue_usd)
    AS affiliate_revenue_share,
  100 * SAFE_DIVIDE(
    revenue.net_revenue_usd
      - LAG(revenue.net_revenue_usd, 365) OVER (ORDER BY revenue.activity_date),
    LAG(revenue.net_revenue_usd, 365) OVER (ORDER BY revenue.activity_date)
  ) AS net_revenue_yoy_pct,
  revenue.stockout_rate,
  revenue.event_name
FROM `raw.revenue_daily` AS revenue
LEFT JOIN marketing USING (activity_date)
LEFT JOIN affiliates USING (activity_date)
ORDER BY revenue.activity_date;

