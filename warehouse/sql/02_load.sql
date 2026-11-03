-- Load staging -> warehouse. Every statement is idempotent, so re-running is safe,
-- and new rows are picked up incrementally (existing business keys are skipped/updated).

-- Date dimension, generated in SQL with a recursive CTE
WITH RECURSIVE d(x) AS (
    SELECT '2024-01-01'
    UNION ALL
    SELECT date(x, '+1 day') FROM d WHERE x < '2027-12-31'
)
INSERT OR IGNORE INTO dim_date (date_key, full_date, year, month, year_month, day_of_week, day_name, is_weekend)
SELECT CAST(strftime('%Y%m%d', x) AS INTEGER),
       x,
       CAST(strftime('%Y', x) AS INTEGER),
       CAST(strftime('%m', x) AS INTEGER),
       strftime('%Y-%m', x),
       CAST(strftime('%w', x) AS INTEGER),
       CASE strftime('%w', x)
            WHEN '0' THEN 'Sunday'   WHEN '1' THEN 'Monday'   WHEN '2' THEN 'Tuesday'
            WHEN '3' THEN 'Wednesday' WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday'
            ELSE 'Saturday' END,
       CASE WHEN strftime('%w', x) IN ('0', '6') THEN 1 ELSE 0 END
FROM d;

-- Plan dimension (type 1: latest values overwrite)
INSERT INTO dim_plan (plan_id, plan_name, price_ngn, duration_months)
SELECT plan_id, plan_name, price_ngn, duration_months FROM stg_plans WHERE true
ON CONFLICT (plan_id) DO UPDATE SET
    plan_name       = excluded.plan_name,
    price_ngn       = excluded.price_ngn,
    duration_months = excluded.duration_months;

-- Member dimension (type 1)
INSERT INTO dim_member (member_id, join_date, plan_key, status)
SELECT s.member_id, s.join_date, p.plan_key, s.status
FROM stg_members s
JOIN dim_plan p ON p.plan_id = s.plan_id
WHERE true
ON CONFLICT (member_id) DO UPDATE SET
    join_date = excluded.join_date,
    plan_key  = excluded.plan_key,
    status    = excluded.status;

-- Facts: insert only rows whose business key is new
INSERT OR IGNORE INTO fact_payment (payment_id, member_key, plan_key, date_key, amount_ngn, method)
SELECT s.payment_id,
       m.member_key,
       m.plan_key,
       CAST(strftime('%Y%m%d', s.paid_at) AS INTEGER),
       s.amount_ngn,
       s.method
FROM stg_payments s
JOIN dim_member m ON m.member_id = s.member_id;

INSERT OR IGNORE INTO fact_checkin (checkin_id, member_key, date_key, hour)
SELECT s.checkin_id,
       m.member_key,
       CAST(strftime('%Y%m%d', s.checked_in_at) AS INTEGER),
       CAST(strftime('%H', s.checked_in_at) AS INTEGER)
FROM stg_checkins s
JOIN dim_member m ON m.member_id = s.member_id;
