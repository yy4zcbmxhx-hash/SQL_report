SET search_path = portfolio, public;
-- Restrict category comparison to the same acquisition era and fully observed 180 days.
CREATE TABLE category_standardized AS
WITH cells AS (
 SELECT cohort,first_category,count(*) AS n,
 count(*) FILTER(WHERE days_to_second<=180)::numeric/count(*) AS rate
 FROM customer_mart WHERE cohort BETWEEN DATE '2013-01-01' AND DATE '2013-06-01'
 GROUP BY 1,2
), weights AS (
 SELECT cohort,sum(n)::numeric/sum(sum(n)) OVER() AS weight FROM cells GROUP BY cohort
)
SELECT first_category,sum(n) AS eligible,sum(rate*weight) AS standardized_rate,
 count(*) AS months FROM cells JOIN weights USING(cohort) GROUP BY first_category;
-- Same-period category mix explains why an aggregate AOV interpretation needs caution.
CREATE TABLE january_category AS
SELECT extract(year FROM s.order_date)::integer AS year,coalesce(p.category,'Unknown') AS category,
 count(DISTINCT s.order_number) AS orders,sum(s.sales_amount) AS revenue
FROM sales_clean s JOIN products p USING(product_key)
WHERE (s.order_date>=DATE '2013-01-01' AND s.order_date<DATE '2013-01-29')
 OR (s.order_date>=DATE '2014-01-01' AND s.order_date<DATE '2014-01-29') GROUP BY 1,2;
CREATE TABLE quality_summary AS
SELECT 'raw_lines'::text AS metric,count(*)::numeric AS value FROM sales_raw UNION ALL
SELECT 'raw_revenue',sum(sales_amount) FROM sales_raw UNION ALL
SELECT 'original_missing_date_lines',count(*) FROM sales_raw WHERE order_date IS NULL UNION ALL
SELECT 'original_missing_date_revenue',sum(sales_amount) FROM sales_raw WHERE order_date IS NULL UNION ALL
SELECT 'recovered_date_lines',count(*) FROM sales_clean WHERE date_recovered UNION ALL
SELECT 'recovered_revenue',sum(sales_amount) FROM sales_clean WHERE date_recovered UNION ALL
SELECT 'quarantine_lines',count(*) FROM quarantine UNION ALL
SELECT 'quarantine_revenue',sum(sales_amount) FROM quarantine UNION ALL
SELECT 'clean_revenue',sum(revenue) FROM orders UNION ALL
SELECT 'legacy_dec_2011_extra_lines',count(*) FROM sales_raw WHERE order_date>DATE '2011-12-01' AND order_date<DATE '2012-01-01' UNION ALL
SELECT 'legacy_dec_2011_extra_revenue',sum(sales_amount) FROM sales_raw WHERE order_date>DATE '2011-12-01' AND order_date<DATE '2012-01-01' UNION ALL
SELECT 'single_old_mislabeled_new',count(*) FROM customer_mart WHERE orders=1 AND first_date<DATE '2013-02-10' UNION ALL
SELECT 'zero_product_cost',count(*) FROM products WHERE cost=0 UNION ALL
SELECT 'sold_lines_zero_cost',count(*) FROM sales_clean JOIN products USING(product_key) WHERE cost=0 UNION ALL
SELECT 'negative_gross_profit_proxy_lines',count(*) FROM sales_clean JOIN products USING(product_key) WHERE sales_amount<quantity*cost UNION ALL
SELECT 'null_birthdates',count(*) FROM customers WHERE birthdate IS NULL UNION ALL
SELECT 'shipping_before_order',count(*) FROM sales_clean WHERE shipping_date<order_date UNION ALL
SELECT 'future_customer_creation',count(*) FROM customers CROSS JOIN settings WHERE create_date>=as_of_date;
-- Cohort-size weighted M1/M3/M6; six-month-mature common set for a comparable profile.
CREATE TABLE cohort_summary AS
SELECT r.month_age,count(*) AS cohorts,sum(r.cohort_size) AS eligible,
 sum(r.active_buyers) AS active,sum(r.active_buyers)::numeric/sum(r.cohort_size) AS retention
FROM cohort_retention r JOIN cohort_retention m USING(cohort)
WHERE r.month_age IN(1,3,6) AND m.month_age=6 AND m.mature GROUP BY 1;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM category_standardized WHERE months<>6) THEN
 RAISE EXCEPTION 'Standardization requires all six cohort cells for every category'; END IF;
END $$;
