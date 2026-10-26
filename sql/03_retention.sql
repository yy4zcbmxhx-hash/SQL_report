SET search_path = portfolio, public;
-- Exact calendar-month retention. A whole target month must be observed, even at age zero.
CREATE TABLE cohort_retention AS
WITH sizes AS (SELECT cohort,count(*) AS cohort_size FROM customer_mart GROUP BY cohort),
 active AS (
 SELECT c.cohort,(extract(year FROM age(date_trunc('month',o.order_date),c.cohort))*12
 +extract(month FROM age(date_trunc('month',o.order_date),c.cohort)))::integer AS month_age,
 count(DISTINCT o.customer_key) AS active_buyers
 FROM orders o JOIN customer_mart c USING(customer_key) GROUP BY 1,2
)
SELECT z.cohort,h.month_age,z.cohort_size,
 z.cohort+(h.month_age+1)*interval '1 month'<=s.as_of_date AS mature,
 CASE WHEN z.cohort+(h.month_age+1)*interval '1 month'<=s.as_of_date
 THEN coalesce(a.active_buyers,0) END AS active_buyers,
 CASE WHEN z.cohort+(h.month_age+1)*interval '1 month'<=s.as_of_date
 THEN coalesce(a.active_buyers,0)::numeric/z.cohort_size END AS retention
FROM sizes z CROSS JOIN generate_series(0,12) h(month_age) CROSS JOIN settings s
LEFT JOIN active a ON a.cohort=z.cohort AND a.month_age=h.month_age;
-- Fixed-horizon cumulative second-order conversion. Immature clients never enter denominator.
CREATE TABLE repeat_horizons AS
SELECT h.days,c.first_category,count(*) AS all_customers,
 count(*) FILTER(WHERE followup_days>=h.days) AS eligible,
 count(*) FILTER(WHERE followup_days>=h.days AND days_to_second<=h.days) AS repeated,
 count(*) FILTER(WHERE followup_days>=h.days AND days_to_second<=h.days)::numeric /
 nullif(count(*) FILTER(WHERE followup_days>=h.days),0) AS repeat_rate
FROM customer_mart c CROSS JOIN (VALUES(30),(90),(180),(365)) h(days) GROUP BY 1,2;
CREATE TABLE repeat_by_cohort AS
SELECT cohort,first_category,count(*) AS eligible,
 count(*) FILTER(WHERE days_to_second<=180) AS repeated,
 count(*) FILTER(WHERE days_to_second<=180)::numeric/count(*) AS repeat_rate
FROM customer_mart WHERE followup_days>=180 GROUP BY 1,2;
-- Kaplan-Meier: event at second order; otherwise administrative censoring at last observed day.
CREATE TABLE km_second_order AS
WITH durations AS (
 SELECT least(coalesce(days_to_second,followup_days),followup_days) AS day,
 days_to_second IS NOT NULL AS event FROM customer_mart
), counts AS (SELECT day,count(*) AS exits,count(*) FILTER(WHERE event) AS events FROM durations GROUP BY day),
 risk AS (SELECT *,sum(exits) OVER(ORDER BY day ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) AS at_risk FROM counts),
 logs AS (SELECT *,sum(CASE WHEN events=at_risk THEN 1 ELSE 0 END) OVER(ORDER BY day) AS all_fail,
 sum(CASE WHEN events<at_risk THEN ln(1-events::numeric/at_risk) ELSE 0 END) OVER(ORDER BY day) AS log_survival FROM risk)
SELECT day,at_risk,events,exits-events AS censored,
 CASE WHEN all_fail>0 THEN 0 ELSE exp(log_survival) END AS survival,
 CASE WHEN all_fail>0 THEN 1 ELSE 1-exp(log_survival) END AS cumulative_repeat FROM logs;
-- Actionable target at day 30, not a retroactively selected set of eventual non-repeaters.
CREATE TABLE campaign_baseline AS
SELECT first_category,count(*) AS eligible,
 count(*) FILTER(WHERE days_to_second BETWEEN 31 AND 120) AS repeat_31_120,
 count(*) FILTER(WHERE days_to_second BETWEEN 31 AND 120)::numeric/count(*) AS baseline_rate,
 avg(o.revenue) FILTER(WHERE c.days_to_second BETWEEN 31 AND 120) AS second_order_aov
FROM customer_mart c LEFT JOIN sequenced_orders o ON c.customer_key=o.customer_key AND o.order_seq=2
WHERE followup_days>=120 AND (days_to_second IS NULL OR days_to_second>30)
GROUP BY first_category;
CREATE TABLE campaign_pool AS
SELECT first_category,count(*) AS customers FROM customer_mart
WHERE tenure_days BETWEEN 30 AND 60 AND orders=1 GROUP BY first_category;
-- Sensitivity: purchase-mix shift, no causal attribution and no SKU association mining.
CREATE TABLE category_year AS
SELECT extract(year FROM s.order_date)::integer AS year,coalesce(p.category,'Unknown') AS category,
 count(DISTINCT s.order_number) AS orders,sum(s.sales_amount) AS revenue
FROM sales_clean s JOIN products p USING(product_key) GROUP BY 1,2;
CREATE TABLE first_to_second AS
SELECT c.first_category,CASE WHEN cardinality(o.categories)>1 THEN 'Mixed' ELSE o.categories[1] END AS second_category,
 count(*) AS customers,avg(o.revenue) AS second_aov
FROM customer_mart c JOIN sequenced_orders o ON c.customer_key=o.customer_key AND o.order_seq=2
WHERE c.followup_days>=180 AND c.days_to_second<=180 GROUP BY 1,2;
ANALYZE;
