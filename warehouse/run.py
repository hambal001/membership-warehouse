"""Run the whole pipeline:  python -m warehouse.run --generate"""
import argparse
import logging
import sqlite3
import sys
from datetime import datetime, timezone

from warehouse import config
from warehouse.checks import DataQualityError, run_checks
from warehouse.generate import generate
from warehouse.stage import stage

log = logging.getLogger("warehouse")


def _sql(name: str) -> str:
    return (config.SQL_DIR / name).read_text(encoding="utf-8")


def run(db_path=None, raw_dir=None, generate_data: bool = False, seed: int = 42) -> dict:
    db_path = db_path or config.DB_PATH
    raw_dir = raw_dir or config.RAW_DIR

    if generate_data:
        log.info("Generated synthetic data: %s", generate(raw_dir, seed=seed))

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_sql("01_schema.sql"))
        staged = stage(conn, raw_dir)
        conn.executescript(_sql("02_load.sql"))
        conn.executescript(_sql("03_marts.sql"))

        status = "ok"
        try:
            passed = run_checks(conn)
        except DataQualityError:
            status = "failed"
            raise
        finally:
            conn.execute(
                "INSERT INTO etl_runs (run_at, staged_rows, rejected_rows, status) VALUES (?, ?, ?, ?)",
                (
                    datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                    sum(staged["staged"].values()),
                    staged["rejected"],
                    status,
                ),
            )
            conn.commit()

        counts = {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("dim_member", "dim_plan", "dim_date", "fact_payment", "fact_checkin", "rejected_rows")
        }
        return {"staged": staged, "warehouse": counts, "checks_passed": len(passed)}
    finally:
        conn.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Membership warehouse pipeline")
    parser.add_argument("--generate", action="store_true", help="generate fresh synthetic CSVs first")
    parser.add_argument("--db", default=None)
    parser.add_argument("--raw-dir", default=None)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        summary = run(args.db, args.raw_dir, generate_data=args.generate)
    except DataQualityError as exc:
        log.error("Data-quality check failed: %s", exc)
        return 2
    log.info("Done: %s", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
