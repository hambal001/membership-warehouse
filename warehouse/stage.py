"""Staging: read raw CSVs, clean them, and quarantine bad rows with a reason.

Nothing is silently dropped. Every rejected record lands in `rejected_rows`
with its source file, id and the reason, so data problems stay visible.
"""
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from warehouse import config

log = logging.getLogger(__name__)


def _read(raw_dir: Path, name: str) -> pd.DataFrame:
    df = pd.read_csv(raw_dir / name, dtype=str, keep_default_na=False)
    return df.apply(lambda col: col.str.strip())


class _Rejects:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def split(self, df: pd.DataFrame, bad: pd.Series, source: str, id_col: str, reason: str) -> pd.DataFrame:
        """Record rows where `bad` is True as rejected and return the remaining good rows."""
        for rid in df.loc[bad, id_col]:
            self.rows.append({"source": source, "record_id": rid, "reason": reason})
        return df.loc[~bad].copy()


def stage(conn, raw_dir) -> dict:
    raw_dir = Path(raw_dir)
    rej = _Rejects()

    # ---- plans -----------------------------------------------------------------------
    plans = _read(raw_dir, "plans.csv")
    plans["price_ngn"] = pd.to_numeric(plans["price_ngn"], errors="coerce")
    plans["duration_months"] = pd.to_numeric(plans["duration_months"], errors="coerce")
    plans = rej.split(plans, plans["price_ngn"].isna() | (plans["price_ngn"] <= 0), "plans", "plan_id", "invalid_price")
    plans = rej.split(plans, plans["duration_months"].isna(), "plans", "plan_id", "invalid_duration")
    plans["duration_months"] = plans["duration_months"].astype(int)

    # ---- members ---------------------------------------------------------------------
    members = _read(raw_dir, "members.csv")
    members["join_date"] = pd.to_datetime(members["join_date"], format="%Y-%m-%d", errors="coerce")
    members["status"] = members["status"].str.lower()
    members = rej.split(members, members["join_date"].isna(), "members", "member_id", "invalid_join_date")
    members = rej.split(members, ~members["plan_id"].isin(plans["plan_id"]), "members", "member_id", "unknown_plan")
    members = rej.split(members, ~members["status"].isin(config.VALID_STATUSES), "members", "member_id", "invalid_status")
    members = rej.split(members, members["member_id"].duplicated(keep="first"), "members", "member_id", "duplicate_id")
    members["join_date"] = members["join_date"].dt.strftime("%Y-%m-%d")

    # ---- payments --------------------------------------------------------------------
    payments = _read(raw_dir, "payments.csv")
    payments["paid_at"] = pd.to_datetime(payments["paid_at"], errors="coerce")
    payments["amount_ngn"] = pd.to_numeric(payments["amount_ngn"], errors="coerce")
    payments = rej.split(payments, payments["paid_at"].isna(), "payments", "payment_id", "invalid_date")
    payments = rej.split(payments, payments["amount_ngn"].isna() | (payments["amount_ngn"] <= 0), "payments", "payment_id", "invalid_amount")
    payments = rej.split(payments, payments["payment_id"].duplicated(keep="first"), "payments", "payment_id", "duplicate_id")
    payments = rej.split(payments, ~payments["member_id"].isin(members["member_id"]), "payments", "payment_id", "unknown_member")
    payments["paid_at"] = payments["paid_at"].dt.strftime("%Y-%m-%d %H:%M:%S")

    # ---- check-ins -------------------------------------------------------------------
    checkins = _read(raw_dir, "checkins.csv")
    checkins["checked_in_at"] = pd.to_datetime(checkins["checked_in_at"], errors="coerce")
    checkins = rej.split(checkins, checkins["checked_in_at"].isna(), "checkins", "checkin_id", "invalid_date")
    checkins = rej.split(checkins, checkins["checkin_id"].duplicated(keep="first"), "checkins", "checkin_id", "duplicate_id")
    checkins = rej.split(checkins, ~checkins["member_id"].isin(members["member_id"]), "checkins", "checkin_id", "unknown_member")
    checkins["checked_in_at"] = checkins["checked_in_at"].dt.strftime("%Y-%m-%d %H:%M:%S")

    # ---- write staging tables + rejects ---------------------------------------------
    for name, df in [("stg_plans", plans), ("stg_members", members), ("stg_payments", payments), ("stg_checkins", checkins)]:
        df.to_sql(name, conn, if_exists="replace", index=False)

    conn.execute("DELETE FROM rejected_rows")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    conn.executemany(
        "INSERT INTO rejected_rows (source, record_id, reason, loaded_at) VALUES (?, ?, ?, ?)",
        [(r["source"], r["record_id"], r["reason"], now) for r in rej.rows],
    )
    conn.commit()

    result = {
        "staged": {"plans": len(plans), "members": len(members), "payments": len(payments), "checkins": len(checkins)},
        "rejected": len(rej.rows),
    }
    log.info("Staged %s, rejected %d", result["staged"], result["rejected"])
    return result
