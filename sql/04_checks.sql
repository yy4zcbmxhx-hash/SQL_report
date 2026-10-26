SET search_path = portfolio, public;
DO $$
BEGIN
 IF (SELECT sum(sales_amount) FROM sales_raw) <>
    (SELECT sum(revenue) FROM orders)+(SELECT coalesce(sum(sales_amount),0) FROM quarantine)
 THEN RAISE EXCEPTION 'Raw/order/quarantine money mismatch'; END IF;
 IF (SELECT sum(revenue) FROM orders) <> (SELECT sum(revenue) FROM customer_mart)
 OR (SELECT sum(revenue) FROM orders) <> (SELECT sum(revenue) FROM monthly)
 OR (SELECT sum(revenue) FROM orders) <> (SELECT sum(revenue) FROM monthly_segments)
 THEN RAISE EXCEPTION 'Mart reconciliation failed'; END IF;
 IF EXISTS(SELECT 1 FROM revenue_bridge WHERE abs(total_change-buyers_effect-frequency_effect-aov_effect)>0.000001)
 OR EXISTS(SELECT 1 FROM monthly_bridge WHERE abs(total_change-buyers_effect-frequency_effect-aov_effect)>0.000001)
 THEN RAISE EXCEPTION 'Revenue bridge residual'; END IF;
 IF EXISTS(SELECT 1 FROM cohort_retention WHERE (NOT mature AND retention IS NOT NULL) OR retention NOT BETWEEN 0 AND 1)
 THEN RAISE EXCEPTION 'Cohort maturity/range failure'; END IF;
 IF EXISTS(SELECT 1 FROM repeat_horizons WHERE repeated>eligible OR eligible>all_customers)
 THEN RAISE EXCEPTION 'Repeat denominator failure'; END IF;
 IF EXISTS(SELECT 1 FROM customer_mart WHERE days_to_second<0 OR days_to_second>followup_days)
 THEN RAISE EXCEPTION 'Invalid second-order interval'; END IF;
 IF EXISTS(SELECT 1 FROM monthly WHERE abs(revenue-buyers*frequency*aov)>0.000001)
 THEN RAISE EXCEPTION 'Revenue identity failed'; END IF;
END $$;
