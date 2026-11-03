"""Data-quality checks run after every load. Any violation fails the run."""
import logging

log = logging.getLogger(__name__)


class DataQualityError(Exception):
    pass


# (check name, SQL returning the number of violating rows - must be 0)
CHECKS = [
    (
        "payments reference an existing member",
        "SELECT COUNT(*) FROM fact_payment f LEFT JOIN dim_member m ON m.member_key = f.member_key "
        "WHERE m.member_key IS NULL",
    ),
    (
        "check-ins reference an existing member",
        "SELECT COUNT(*) FROM fact_checkin f LEFT JOIN dim_member m ON m.member_key = f.member_key "
        "WHERE m.member_key IS NULL",
    ),
    (
        "facts reference an existing date",
        "SELECT (SELECT COUNT(*) FROM fact_payment f LEFT JOIN dim_date d ON d.date_key = f.date_key WHERE d.date_key IS NULL)"
        " + (SELECT COUNT(*) FROM fact_checkin f LEFT JOIN dim_date d ON d.date_key = f.date_key WHERE d.date_key IS NULL)",
    ),
    (
        "all payment amounts are positive",
        "SELECT COUNT(*) FROM fact_payment WHERE amount_ngn <= 0",
    ),
    (
        "every staged payment reached the warehouse",
        "SELECT COUNT(*) FROM stg_payments s LEFT JOIN fact_payment f ON f.payment_id = s.payment_id "
        "WHERE f.payment_id IS NULL",
    ),
    (
        "every staged check-in reached the warehouse",
        "SELECT COUNT(*) FROM stg_checkins s LEFT JOIN fact_checkin f ON f.checkin_id = s.checkin_id "
        "WHERE f.checkin_id IS NULL",
    ),
    (
        "every staged member reached the warehouse",
        "SELECT COUNT(*) FROM stg_members s LEFT JOIN dim_member m ON m.member_id = s.member_id "
        "WHERE m.member_id IS NULL",
    ),
    (
        "no member joined in the future relative to last activity",
        "SELECT COUNT(*) FROM fact_checkin f JOIN dim_member m ON m.member_key = f.member_key "
        "JOIN dim_date d ON d.date_key = f.date_key WHERE d.full_date < m.join_date",
    ),
]


def run_checks(conn) -> list[str]:
    """Run all checks. Returns the names of passed checks, raises DataQualityError on failure."""
    failures, passed = [], []
    for name, sql in CHECKS:
        violations = conn.execute(sql).fetchone()[0]
        if violations:
            failures.append(f"{name}: {violations} violation(s)")
        else:
            passed.append(name)
    if failures:
        raise DataQualityError("; ".join(failures))
    log.info("All %d data-quality checks passed", len(passed))
    return passed
