"""Generate a realistic *synthetic* gym-membership dataset as raw CSV files.

The data is fake (no real people) but deliberately messy: it contains duplicate rows,
negative amounts, invalid dates and orphan references, so the pipeline's cleaning and
data-quality logic has something real to catch. Output is deterministic for a given seed.
"""
import csv
import datetime as dt
import random
from pathlib import Path

PLANS = [
    # plan_id, plan_name, price_ngn (per billing period), duration_months
    ("P1", "Monthly", 15000, 1),
    ("P2", "Quarterly", 40000, 3),
    ("P3", "Student Monthly", 10000, 1),
    ("P4", "Annual", 150000, 12),
    ("P5", "Couples Monthly", 25000, 1),
]
PLAN_WEIGHTS = [40, 15, 25, 5, 15]
METHODS = ["transfer", "cash", "pos"]
HOURS = list(range(5, 22))
HOUR_WEIGHTS = [3, 8, 9, 6, 3, 2, 2, 2, 3, 5, 9, 10, 9, 5, 3, 2, 1]  # peaks around 7am and 4pm


def _write(path: Path, header: list[str], rows: list[list]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def generate(out_dir, seed: int = 42, n_members: int = 300, as_of: dt.date = dt.date(2026, 11, 1)) -> dict:
    rng = random.Random(seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    members, payments, checkins = [], [], []
    start = dt.date(2025, 1, 1)
    span = (as_of - start).days - 14
    pay_n = chk_n = 0

    for i in range(1, n_members + 1):
        member_id = f"M{i:04d}"
        join = start + dt.timedelta(days=rng.randint(0, span))
        plan = rng.choices(PLANS, weights=PLAN_WEIGHTS)[0]
        tenure = int(rng.expovariate(1 / 240)) + 30
        end = join + dt.timedelta(days=tenure)
        active = end > as_of
        last_day = min(end, as_of)
        members.append([member_id, join.isoformat(), plan[0], "active" if active else "expired"])

        k = 0
        pay_day = join
        while pay_day < last_day:
            pay_n += 1
            ts = dt.datetime.combine(pay_day, dt.time(rng.randint(8, 18), rng.randint(0, 59), 0))
            payments.append([f"PAY{pay_n:06d}", member_id, ts.isoformat(sep=" "), plan[2], rng.choice(METHODS)])
            k += 1
            pay_day = join + dt.timedelta(days=30 * plan[3] * k)

        rate = rng.uniform(0.6, 4.0) / 7  # average visits per day
        stop = last_day
        if active and rng.random() < 0.2:  # these members quietly stop coming (churn risk)
            stop = min(stop, as_of - dt.timedelta(days=rng.randint(25, 60)))
        day = join
        while day < stop:
            if rng.random() < rate:
                chk_n += 1
                hour = rng.choices(HOURS, weights=HOUR_WEIGHTS)[0]
                ts = dt.datetime.combine(day, dt.time(hour, rng.randint(0, 59), 0))
                checkins.append([f"CHK{chk_n:06d}", member_id, ts.isoformat(sep=" ")])
            day += dt.timedelta(days=1)

    # ---- inject realistic data-quality problems -------------------------------------
    for row in rng.sample(payments, max(1, len(payments) // 100)):          # duplicate payments
        payments.append(list(row))
    for _ in range(3):                                                       # negative amounts
        pay_n += 1
        payments.append([f"PAY{pay_n:06d}", "M0001", "2026-01-05 10:00:00", -15000, "cash"])
    for row in rng.sample(checkins, 10):                                     # duplicate check-ins
        checkins.append(list(row))
    for i in range(5):                                                       # unknown member
        chk_n += 1
        checkins.append([f"CHK{chk_n:06d}", "M9999", f"2026-0{i + 1}-10 07:30:00"])
    members.append([f"M{n_members + 1:04d}", "N/A", "P1", "active"])         # invalid join date
    members.append([f"M{n_members + 2:04d}", "", "P2", "active"])            # missing join date

    _write(out / "plans.csv", ["plan_id", "plan_name", "price_ngn", "duration_months"], [list(p) for p in PLANS])
    _write(out / "members.csv", ["member_id", "join_date", "plan_id", "status"], members)
    _write(out / "payments.csv", ["payment_id", "member_id", "paid_at", "amount_ngn", "method"], payments)
    _write(out / "checkins.csv", ["checkin_id", "member_id", "checked_in_at"], checkins)
    return {"members": len(members), "payments": len(payments), "checkins": len(checkins)}


if __name__ == "__main__":
    print(generate("data/raw"))
