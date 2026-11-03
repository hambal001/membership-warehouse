-- Star schema: 3 dimensions + 2 fact tables, plus audit tables.

CREATE TABLE IF NOT EXISTS dim_date (
    date_key     INTEGER PRIMARY KEY,          -- yyyymmdd
    full_date    TEXT NOT NULL UNIQUE,
    year         INTEGER NOT NULL,
    month        INTEGER NOT NULL,
    year_month   TEXT NOT NULL,
    day_of_week  INTEGER NOT NULL,             -- 0 = Sunday
    day_name     TEXT NOT NULL,
    is_weekend   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_plan (
    plan_key         INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id          TEXT NOT NULL UNIQUE,
    plan_name        TEXT NOT NULL,
    price_ngn        REAL NOT NULL,
    duration_months  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_member (
    member_key  INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id   TEXT NOT NULL UNIQUE,
    join_date   TEXT NOT NULL,
    plan_key    INTEGER NOT NULL REFERENCES dim_plan (plan_key),
    status      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_payment (
    payment_key  INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_id   TEXT NOT NULL UNIQUE,
    member_key   INTEGER NOT NULL REFERENCES dim_member (member_key),
    plan_key     INTEGER NOT NULL REFERENCES dim_plan (plan_key),
    date_key     INTEGER NOT NULL REFERENCES dim_date (date_key),
    amount_ngn   REAL NOT NULL,
    method       TEXT
);

CREATE TABLE IF NOT EXISTS fact_checkin (
    checkin_key  INTEGER PRIMARY KEY AUTOINCREMENT,
    checkin_id   TEXT NOT NULL UNIQUE,
    member_key   INTEGER NOT NULL REFERENCES dim_member (member_key),
    date_key     INTEGER NOT NULL REFERENCES dim_date (date_key),
    hour         INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_fact_payment_member ON fact_payment (member_key);
CREATE INDEX IF NOT EXISTS ix_fact_payment_date   ON fact_payment (date_key);
CREATE INDEX IF NOT EXISTS ix_fact_checkin_member ON fact_checkin (member_key);
CREATE INDEX IF NOT EXISTS ix_fact_checkin_date   ON fact_checkin (date_key);

-- Audit tables
CREATE TABLE IF NOT EXISTS rejected_rows (
    source     TEXT NOT NULL,
    record_id  TEXT,
    reason     TEXT NOT NULL,
    loaded_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS etl_runs (
    run_at         TEXT NOT NULL,
    staged_rows    INTEGER NOT NULL,
    rejected_rows  INTEGER NOT NULL,
    status         TEXT NOT NULL
);
