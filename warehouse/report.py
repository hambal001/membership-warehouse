"""Print the headline numbers from the marts:  python -m warehouse.report"""
import sqlite3

import pandas as pd

from warehouse import config


def main() -> None:
    conn = sqlite3.connect(config.DB_PATH)
    pd.set_option("display.width", 120)

    print("\n== Revenue by month (last 6 months, NGN) ==")
    print(pd.read_sql(
        "SELECT year_month, SUM(revenue_ngn) AS revenue_ngn, SUM(payments) AS payments "
        "FROM mart_monthly_revenue GROUP BY year_month ORDER BY year_month DESC LIMIT 6", conn
    ).to_string(index=False))

    print("\n== Members at risk of churning (active, no visit for 21+ days) ==")
    print(pd.read_sql(
        "SELECT COUNT(*) AS active_members, SUM(at_risk) AS at_risk_members, "
        "ROUND(100.0 * SUM(at_risk) / COUNT(*), 1) AS pct_of_active FROM mart_member_activity "
        "WHERE status = 'active'", conn
    ).to_string(index=False))

    print("\n== Busiest hours ==")
    print(pd.read_sql(
        "SELECT hour, SUM(checkins) AS checkins FROM mart_peak_hours GROUP BY hour "
        "ORDER BY checkins DESC LIMIT 5", conn
    ).to_string(index=False))

    print("\n== Retention by cohort: % of cohort still visiting at month N (first 4 cohorts) ==")
    print(pd.read_sql(
        "SELECT cohort_month, month_n, retention_pct FROM mart_cohort_retention "
        "WHERE month_n IN (0, 1, 3, 6) AND cohort_month IN "
        "(SELECT DISTINCT cohort_month FROM mart_cohort_retention ORDER BY cohort_month LIMIT 4) "
        "ORDER BY cohort_month, month_n", conn
    ).to_string(index=False))
    conn.close()


if __name__ == "__main__":
    main()
