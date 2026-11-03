import sqlite3

import pytest

PLANS = """plan_id,plan_name,price_ngn,duration_months
P1,Monthly,10000,1
P3,Quarterly,27000,3
"""

MEMBERS = """member_id,join_date,plan_id,status
M1,2026-01-10,P1,active
M2,2026-01-20,P1,active
M3,2026-02-01,P3,expired
M4,oops,P1,active
M5,2026-02-05,PX,active
M1,2026-01-10,P1,active
"""

PAYMENTS = """payment_id,member_id,paid_at,amount_ngn,method
PAY1,M1,2026-01-10 10:00:00,10000,cash
PAY2,M1,2026-02-10 10:00:00,10000,transfer
PAY3,M2,2026-01-20 09:00:00,10000,pos
PAY4,M3,2026-02-01 08:00:00,27000,transfer
PAY5,M1,2026-03-10 10:00:00,-5,cash
PAY1,M1,2026-01-10 10:00:00,10000,cash
PAY6,M9,2026-02-01 10:00:00,10000,cash
"""

CHECKINS = """checkin_id,member_id,checked_in_at
C1,M1,2026-03-01 07:00:00
C2,M1,2026-03-15 18:00:00
C3,M2,2026-02-01 07:00:00
C4,M3,2026-02-02 06:00:00
C5,M9,2026-02-03 06:00:00
C1,M1,2026-03-01 07:00:00
"""


@pytest.fixture
def raw_dir(tmp_path):
    d = tmp_path / "raw"
    d.mkdir()
    (d / "plans.csv").write_text(PLANS)
    (d / "members.csv").write_text(MEMBERS)
    (d / "payments.csv").write_text(PAYMENTS)
    (d / "checkins.csv").write_text(CHECKINS)
    return d


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


def query(db_path, sql):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()
