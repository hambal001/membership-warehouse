import sqlite3

import pytest

from tests.conftest import query
from warehouse.checks import DataQualityError, run_checks
from warehouse.generate import generate
from warehouse.run import run


def test_staging_rejects_bad_rows_with_reasons(raw_dir, db_path):
    summary = run(db_path, raw_dir)
    assert summary["staged"]["staged"] == {"plans": 2, "members": 3, "payments": 4, "checkins": 4}
    assert summary["staged"]["rejected"] == 8

    reasons = {(s, r) for s, r in query(db_path, "SELECT source, reason FROM rejected_rows")}
    assert ("members", "invalid_join_date") in reasons
    assert ("members", "unknown_plan") in reasons
    assert ("members", "duplicate_id") in reasons
    assert ("payments", "invalid_amount") in reasons
    assert ("payments", "unknown_member") in reasons
    assert ("checkins", "duplicate_id") in reasons


def test_pipeline_is_idempotent(raw_dir, db_path):
    run(db_path, raw_dir)
    run(db_path, raw_dir)  # same input twice
    assert query(db_path, "SELECT COUNT(*) FROM dim_member") == [(3,)]
    assert query(db_path, "SELECT COUNT(*) FROM fact_payment") == [(4,)]
    assert query(db_path, "SELECT COUNT(*) FROM fact_checkin") == [(4,)]
    assert query(db_path, "SELECT COUNT(*) FROM etl_runs") == [(2,)]


def test_incremental_load_adds_only_new_rows(raw_dir, db_path):
    run(db_path, raw_dir)
    with open(raw_dir / "payments.csv", "a") as fh:
        fh.write("PAY7,M2,2026-02-20 09:00:00,10000,pos\n")
    run(db_path, raw_dir)
    assert query(db_path, "SELECT COUNT(*) FROM fact_payment") == [(5,)]


def test_dimension_update_overwrites_status(raw_dir, db_path):
    run(db_path, raw_dir)
    text = (raw_dir / "members.csv").read_text().replace("M2,2026-01-20,P1,active", "M2,2026-01-20,P1,expired")
    (raw_dir / "members.csv").write_text(text)
    run(db_path, raw_dir)
    assert query(db_path, "SELECT status FROM dim_member WHERE member_id='M2'") == [("expired",)]
    assert query(db_path, "SELECT COUNT(*) FROM dim_member") == [(3,)]  # updated, not duplicated


def test_monthly_revenue_mart(raw_dir, db_path):
    run(db_path, raw_dir)
    rows = query(
        db_path,
        "SELECT year_month, plan_name, payments, revenue_ngn FROM mart_monthly_revenue "
        "ORDER BY year_month, plan_name",
    )
    assert rows == [
        ("2026-01", "Monthly", 2, 20000.0),
        ("2026-02", "Monthly", 1, 10000.0),
        ("2026-02", "Quarterly", 1, 27000.0),
    ]


def test_member_activity_and_churn_flag(raw_dir, db_path):
    run(db_path, raw_dir)
    rows = dict(
        (m, (days, risk))
        for m, days, risk in query(
            db_path, "SELECT member_id, days_since_last_visit, at_risk FROM mart_member_activity"
        )
    )
    assert rows["M1"] == (0, 0)    # visited on the as-of date
    assert rows["M2"] == (42, 1)   # active but silent for 42 days -> at risk
    assert rows["M3"][1] == 0      # expired members are never flagged


def test_cohort_retention_mart(raw_dir, db_path):
    run(db_path, raw_dir)
    rows = query(
        db_path,
        "SELECT cohort_month, month_n, cohort_members, active_members, retention_pct "
        "FROM mart_cohort_retention WHERE cohort_month = '2026-01' ORDER BY month_n",
    )
    # Jan cohort = M1 + M2. M2 visited 12 days after joining (month 0); M1 visited ~50 and ~64 days later.
    assert rows[0] == ("2026-01", 0, 2, 1, 50.0)
    assert all(r[2] == 2 for r in rows)


def test_quality_checks_catch_broken_data(raw_dir, db_path):
    run(db_path, raw_dir)
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM dim_member WHERE member_id = 'M1'")  # create orphan facts
    conn.commit()
    with pytest.raises(DataQualityError) as exc:
        run_checks(conn)
    assert "payments reference an existing member" in str(exc.value)
    conn.close()


def test_generator_is_deterministic(tmp_path):
    a = generate(tmp_path / "a", seed=7, n_members=40)
    b = generate(tmp_path / "b", seed=7, n_members=40)
    assert a == b
    for name in ("members.csv", "payments.csv", "checkins.csv"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_full_run_on_generated_messy_data(tmp_path):
    raw = tmp_path / "raw"
    db = str(tmp_path / "wh.db")
    generate(raw, seed=1, n_members=80)
    summary = run(db, raw)
    assert summary["checks_passed"] == 8
    assert summary["staged"]["rejected"] > 0          # injected problems were caught
    assert summary["warehouse"]["fact_checkin"] > 0
    assert query(db, "SELECT COUNT(*) FROM fact_payment WHERE amount_ngn <= 0") == [(0,)]
