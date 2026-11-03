"""Paths and defaults. Override with environment variables."""
import os
from pathlib import Path

DB_PATH = os.getenv("WAREHOUSE_DB", "warehouse.db")
RAW_DIR = Path(os.getenv("RAW_DIR", "data/raw"))
SQL_DIR = Path(__file__).parent / "sql"

VALID_STATUSES = {"active", "expired"}
AT_RISK_DAYS = 21  # active member with no visit for this many days is flagged
