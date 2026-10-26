SET search_path = portfolio, public;
-- Grain: one order. A null date can be recovered only from the same order.
CREATE TABLE order_quality AS
SELECT order_number, count(DISTINCT customer_key) AS customer_count,
 count(DISTINCT order_date) AS date_count, min(order_date) AS resolved_date,
 count(*) FILTER(WHERE order_date IS NULL) AS missing_lines
FROM sales_raw GROUP BY order_number;
ALTER TABLE order_quality ADD PRIMARY KEY(order_number);
CREATE VIEW quarantine AS
SELECT s.*, CASE WHEN q.customer_count <> 1 THEN 'conflicting_customer'
 WHEN q.date_count > 1 THEN 'conflicting_date' ELSE 'missing_order_date' END AS reason
FROM sales_raw s JOIN order_quality q USING(order_number)
WHERE q.customer_count <> 1 OR q.date_count <> 1;
CREATE TABLE sales_clean AS
SELECT s.order_number,s.product_key,s.customer_key,q.resolved_date AS order_date,
 s.shipping_date,s.due_date,s.sales_amount,s.quantity,s.price,
 s.order_date IS NULL AS date_recovered
FROM sales_raw s JOIN order_quality q USING(order_number)
WHERE q.customer_count=1 AND q.date_count=1;
ALTER TABLE sales_clean ADD PRIMARY KEY(order_number,product_key);
-- Exclusive observation end = day after the latest observed order, not NOW or shipping date.
CREATE TABLE settings AS SELECT min(order_date) AS observation_start,
 max(order_date)+1 AS as_of_date FROM sales_clean;
CREATE TABLE orders AS
SELECT s.order_number,s.customer_key,s.order_date,
 sum(s.sales_amount) AS revenue,sum(s.quantity) AS units,count(*) AS lines,
 array_agg(DISTINCT coalesce(p.category,'Unknown') ORDER BY coalesce(p.category,'Unknown')) AS categories,
 bool_or(s.date_recovered) AS date_recovered
FROM sales_clean s JOIN products p USING(product_key)
GROUP BY s.order_number,s.customer_key,s.order_date;
ALTER TABLE orders ADD PRIMARY KEY(order_number);
CREATE INDEX orders_customer_date_idx ON orders(customer_key,order_date,order_number);
CREATE INDEX orders_date_idx ON orders(order_date);
CREATE VIEW sequenced_orders AS
SELECT *,row_number() OVER(PARTITION BY customer_key ORDER BY order_date,order_number) AS order_seq
FROM orders;
-- Grain: one customer with at least one eligible order. Same-day ties use order_number.
CREATE TABLE customer_mart AS
WITH a AS (
 SELECT customer_key,min(order_date) AS first_date,max(order_date) AS last_date,
 max(order_date) FILTER(WHERE order_seq=2) AS second_date,
 count(*) AS orders,sum(revenue) AS revenue
 FROM sequenced_orders GROUP BY customer_key
)
SELECT a.*,s.as_of_date,s.as_of_date-1-first_date AS followup_days,
 s.as_of_date-last_date AS recency_days,s.as_of_date-first_date AS tenure_days,
 second_date-first_date AS days_to_second,
 date_trunc('month',first_date)::date AS cohort,
 CASE WHEN cardinality(o.categories)>1 THEN 'Mixed' ELSE o.categories[1] END AS first_category,
 extract(year FROM age(s.as_of_date,c.birthdate)) AS age_at_snapshot,
 s.as_of_date-first_date <= 30 AS new_last_30d
FROM a JOIN sequenced_orders o ON a.customer_key=o.customer_key AND o.order_seq=1
JOIN customers c ON c.customer_key=a.customer_key CROSS JOIN settings s;
ALTER TABLE customer_mart ADD PRIMARY KEY(customer_key);
-- Grain: month x mutually exclusive customer status in that month.
CREATE TABLE monthly_segments AS
SELECT date_trunc('month',o.order_date)::date AS month,
 CASE WHEN date_trunc('month',o.order_date)::date=c.cohort THEN 'New' ELSE 'Returning' END AS segment,
 count(DISTINCT o.customer_key) AS buyers,count(*) AS orders,sum(o.revenue) AS revenue,
 count(*)::numeric/count(DISTINCT o.customer_key) AS frequency,
 sum(o.revenue)/count(*) AS aov
FROM orders o JOIN customer_mart c USING(customer_key) GROUP BY 1,2;
CREATE TABLE monthly AS
SELECT date_trunc('month',o.order_date)::date AS month,
 count(DISTINCT o.customer_key) AS buyers,count(*) AS orders,sum(o.revenue) AS revenue,
 count(*)::numeric/count(DISTINCT o.customer_key) AS frequency,sum(o.revenue)/count(*) AS aov,
 date_trunc('month',o.order_date)::date >= s.observation_start
 AND date_trunc('month',o.order_date)::date+interval '1 month' <= s.as_of_date AS full_month
FROM orders o CROSS JOIN settings s GROUP BY 1,s.observation_start,s.as_of_date;
ALTER TABLE monthly ADD PRIMARY KEY(month);
-- Like-for-like years plus exactly matched January 1-28 windows.
CREATE TABLE period_metrics AS
WITH windows(label,start_date,end_date) AS (VALUES
 ('2011',date '2011-01-01',date '2012-01-01'),
 ('2012',date '2012-01-01',date '2013-01-01'),
 ('2013',date '2013-01-01',date '2014-01-01'),
 ('Jan 1-28 2013',date '2013-01-01',date '2013-01-29'),
 ('Jan 1-28 2014',date '2014-01-01',date '2014-01-29'))
SELECT label,start_date,end_date,count(DISTINCT customer_key) AS buyers,count(*) AS orders,
 sum(revenue) AS revenue,count(*)::numeric/count(DISTINCT customer_key) AS frequency,
 sum(revenue)/count(*) AS aov
FROM windows JOIN orders ON order_date>=start_date AND order_date<end_date GROUP BY 1,2,3;
-- Exact sequential bridge R=B*F*A. Order of substitution is explicit and affects contributions.
CREATE TABLE revenue_bridge AS
WITH pairs AS (
 SELECT '2012 -> 2013'::text AS comparison,a.*,b.buyers AS b1,b.frequency AS f1,b.aov AS a1,b.revenue AS r1
 FROM period_metrics a CROSS JOIN period_metrics b WHERE a.label='2012' AND b.label='2013'
 UNION ALL
 SELECT 'Jan 1-28: 2013 -> 2014',a.*,b.buyers,b.frequency,b.aov,b.revenue
 FROM period_metrics a CROSS JOIN period_metrics b WHERE a.label='Jan 1-28 2013' AND b.label='Jan 1-28 2014'
)
SELECT comparison,revenue AS revenue_before,r1 AS revenue_after,
 (b1-buyers)*frequency*aov AS buyers_effect,
 b1*(f1-frequency)*aov AS frequency_effect,
 b1*f1*(a1-aov) AS aov_effect,r1-revenue AS total_change FROM pairs;
CREATE TABLE monthly_bridge AS
WITH a AS (SELECT *,lag(buyers) OVER w AS b0,lag(frequency) OVER w AS f0,
 lag(aov) OVER w AS a0,lag(revenue) OVER w AS r0,lag(full_month) OVER w AS previous_full
 FROM monthly WINDOW w AS (ORDER BY month))
SELECT month,revenue-r0 AS total_change,(buyers-b0)*f0*a0 AS buyers_effect,
 buyers*(frequency-f0)*a0 AS frequency_effect,buyers*frequency*(aov-a0) AS aov_effect,
 full_month AND previous_full AS comparable FROM a;
