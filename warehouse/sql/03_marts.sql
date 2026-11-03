-- Analytics marts: business-facing views on top of the star schema.

DROP VIEW IF EXISTS mart_monthly_revenue;
CREATE VIEW mart_monthly_revenue AS
SELECT d.year_month,
       p.plan_name,
       COUNT(*)          AS payments,
       SUM(f.amount_ngn) AS revenue_ngn
FROM fact_payment f
JOIN dim_date d ON d.date_key = f.date_key
JOIN dim_plan p ON p.plan_key = f.plan_key
GROUP BY d.year_month, p.plan_name;

-- One row per member: engagement and churn-risk flag.
-- "As of" date = the latest check-in in the data, so results are reproducible.
DROP VIEW IF EXISTS mart_member_activity;
CREATE VIEW mart_member_activity AS
WITH visits AS (
    SELECT f.member_key,
           COUNT(*)           AS total_checkins,
           MAX(d.full_date)   AS last_checkin_date
    FROM fact_checkin f
    JOIN dim_date d ON d.date_key = f.date_key
    GROUP BY f.member_key
),
asof AS (
    SELECT MAX(d.full_date) AS as_of
    FROM fact_checkin f
    JOIN dim_date d ON d.date_key = f.date_key
)
SELECT m.member_id,
       m.status,
       m.join_date,
       COALESCE(v.total_checkins, 0) AS total_checkins,
       v.last_checkin_date,
       CAST(julianday(a.as_of) - julianday(COALESCE(v.last_checkin_date, m.join_date)) AS INTEGER)
           AS days_since_last_visit,
       CASE WHEN m.status = 'active'
             AND julianday(a.as_of) - julianday(COALESCE(v.last_checkin_date, m.join_date)) > 21
            THEN 1 ELSE 0 END AS at_risk
FROM dim_member m
LEFT JOIN visits v ON v.member_key = m.member_key
CROSS JOIN asof a;

-- Cohort retention: of the members who joined in a month, how many visited in month N after joining?
DROP VIEW IF EXISTS mart_cohort_retention;
CREATE VIEW mart_cohort_retention AS
WITH cohort_size AS (
    SELECT strftime('%Y-%m', join_date) AS cohort_month, COUNT(*) AS members
    FROM dim_member
    GROUP BY 1
),
activity AS (
    SELECT strftime('%Y-%m', m.join_date) AS cohort_month,
           CAST((julianday(d.full_date) - julianday(m.join_date)) / 30 AS INTEGER) AS month_n,
           COUNT(DISTINCT m.member_key) AS active_members
    FROM fact_checkin f
    JOIN dim_member m ON m.member_key = f.member_key
    JOIN dim_date d   ON d.date_key = f.date_key
    WHERE d.full_date >= m.join_date
    GROUP BY 1, 2
)
SELECT a.cohort_month,
       a.month_n,
       c.members AS cohort_members,
       a.active_members,
       ROUND(100.0 * a.active_members / c.members, 1) AS retention_pct
FROM activity a
JOIN cohort_size c ON c.cohort_month = a.cohort_month;

DROP VIEW IF EXISTS mart_peak_hours;
CREATE VIEW mart_peak_hours AS
SELECT d.day_name, d.day_of_week, f.hour, COUNT(*) AS checkins
FROM fact_checkin f
JOIN dim_date d ON d.date_key = f.date_key
GROUP BY d.day_name, d.day_of_week, f.hour;
