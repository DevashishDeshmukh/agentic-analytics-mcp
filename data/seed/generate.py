"""Generate a deterministic synthetic e-commerce warehouse (~950k rows).

Planted data issues (documented in data/docs/issues, used by evals):
  ISSUE-001  orders.channel is NULL for orders before 2023-03-01
  ISSUE-002  refunds.reason is NULL for refunds before 2024-01-01
  ISSUE-003  customers.region_id is NULL for ~2% of customers

Usage:
    uv run python data/seed/generate.py            # uses ADMIN_DSN from .env
"""

from __future__ import annotations

import os
import random
import time
from datetime import date, datetime, timedelta

import psycopg
from dotenv import load_dotenv

SEED = 42
N_CUSTOMERS = 50_000
N_PRODUCTS = 300
N_ORDERS = 200_000

START = date(2023, 1, 1)
END = date(2025, 12, 31)
CHANNEL_BACKFILL_DATE = date(2023, 3, 1)
REASON_TRACKING_DATE = date(2024, 1, 1)

REGIONS = [
    (1, "North America East", "United States"),
    (2, "North America West", "United States"),
    (3, "Europe North", "Germany"),
    (4, "Europe South", "Spain"),
    (5, "APAC", "Singapore"),
    (6, "India", "India"),
    (7, "LATAM", "Brazil"),
    (8, "Middle East", "United Arab Emirates"),
]

CATEGORIES = {
    "Electronics": (40, 1500),
    "Books": (8, 60),
    "Home": (15, 400),
    "Clothing": (10, 200),
    "Sports": (12, 500),
    "Beauty": (5, 120),
    "Toys": (8, 150),
    "Grocery": (2, 40),
}

PRODUCT_WORDS = [
    "Classic", "Pro", "Ultra", "Eco", "Smart", "Mini", "Max", "Prime", "Lite", "Plus",
    "Urban", "Nordic", "Vintage", "Fresh", "Rapid", "Zen", "Bold", "Pure", "Core", "Edge",
]

FIRST_NAMES = [
    "Aarav", "Priya", "James", "Maria", "Wei", "Fatima", "Lucas", "Sofia", "Kenji", "Amara",
    "Noah", "Olivia", "Arjun", "Elena", "Omar", "Chloe", "Mateo", "Hana", "Liam", "Zara",
    "Ethan", "Isabel", "Ravi", "Anya", "Diego", "Mei", "Samuel", "Leila", "Jonas", "Nina",
]
LAST_NAMES = [
    "Sharma", "Smith", "Garcia", "Chen", "Khan", "Silva", "Tanaka", "Okafor", "Muller",
    "Rossi", "Patel", "Kim", "Novak", "Haddad", "Johansson", "Lopez", "Ivanova", "Mensah",
    "Dubois", "Nguyen", "Brown", "Costa", "Ali", "Fischer", "Reddy",
]

SEGMENTS = [("consumer", 0.80), ("small_business", 0.15), ("enterprise", 0.05)]
CHANNELS = [("web", 0.45), ("mobile_app", 0.35), ("marketplace", 0.12), ("store", 0.08)]
STATUSES = [
    ("completed", 0.78), ("shipped", 0.06), ("returned", 0.05),
    ("cancelled", 0.07), ("placed", 0.04),
]
PAYMENT_METHODS = [
    ("credit_card", 0.50), ("debit_card", 0.20), ("paypal", 0.18),
    ("gift_card", 0.07), ("bank_transfer", 0.05),
]
REFUND_REASONS = ["damaged", "wrong_item", "late_delivery", "changed_mind", "not_as_described"]


def pick(rng: random.Random, weighted: list[tuple[str, float]]) -> str:
    values, weights = zip(*weighted)
    return rng.choices(values, weights=weights, k=1)[0]


def rand_date(rng: random.Random, lo: date, hi: date) -> date:
    return lo + timedelta(days=rng.randint(0, (hi - lo).days))


def growth_date(rng: random.Random, lo: date, hi: date) -> date:
    """Order dates skewed toward later dates (business growth) with a Q4 bump."""
    span = (hi - lo).days
    while True:
        d = lo + timedelta(days=int(span * (rng.random() ** 0.8)))
        if d.month in (11, 12) or rng.random() < 0.82:
            return d


def money(x: float) -> str:
    return f"{x:.2f}"


def generate(rng: random.Random) -> dict[str, list[tuple]]:
    data: dict[str, list[tuple]] = {}
    data["regions"] = REGIONS

    customers = []
    signup_lo = date(2022, 1, 1)
    for cid in range(1, N_CUSTOMERS + 1):
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        region = None if rng.random() < 0.02 else rng.randint(1, len(REGIONS))
        customers.append((
            cid, first, last, f"{first.lower()}.{last.lower()}{cid}@example.com",
            region, pick(rng, SEGMENTS), rand_date(rng, signup_lo, END),
        ))
    data["customers"] = customers

    products, prices = [], {}
    cats = list(CATEGORIES)
    for pid in range(1, N_PRODUCTS + 1):
        cat = cats[(pid - 1) % len(cats)]
        lo, hi = CATEGORIES[cat]
        price = round(lo + (hi - lo) * rng.random() ** 2, 2)
        prices[pid] = price
        name = f"{rng.choice(PRODUCT_WORDS)} {cat.removesuffix('s')} {pid}"
        products.append((pid, name, cat, money(price), rng.random() < 0.85))
    data["products"] = products

    # Pareto-ish customer popularity so some customers repeat a lot.
    weights = [1 / (i ** 0.6) for i in range(1, N_CUSTOMERS + 1)]
    rng.shuffle(weights)
    order_customers = rng.choices(range(1, N_CUSTOMERS + 1), weights=weights, k=N_ORDERS)

    orders, items, payments, refunds = [], [], [], []
    item_id = payment_id = refund_id = 1
    for oid, cid in enumerate(order_customers, start=1):
        signup = customers[cid - 1][6]
        lo = max(signup, START)
        lo = min(lo, END)
        odate = growth_date(rng, lo, END) if lo < END else END
        status = pick(rng, STATUSES)
        if odate > END - timedelta(days=10) and status == "completed":
            status = rng.choice(["placed", "shipped"])
        channel = None if odate < CHANNEL_BACKFILL_DATE else pick(rng, CHANNELS)

        total = 0.0
        for _ in range(rng.choices([1, 2, 3, 4, 5], weights=[35, 30, 18, 10, 7])[0]):
            pid = rng.randint(1, N_PRODUCTS)
            qty = rng.choices([1, 2, 3, 4], weights=[70, 20, 7, 3])[0]
            unit = round(prices[pid] * (1 - rng.choice([0, 0, 0, 0.05, 0.1, 0.2])), 2)
            items.append((item_id, oid, pid, qty, money(unit)))
            item_id += 1
            total += qty * unit
        total = round(total, 2)
        orders.append((oid, cid, odate, status, channel, money(total)))

        if status != "cancelled":
            paid_at = datetime.combine(odate, datetime.min.time()) + timedelta(
                minutes=rng.randint(1, 600)
            )
            payments.append((payment_id, oid, pick(rng, PAYMENT_METHODS), money(total), paid_at))
            payment_id += 1

        refund_amount = None
        if status == "returned":
            refund_amount = total
        elif status == "completed" and rng.random() < 0.02:
            refund_amount = round(total * rng.choice([0.1, 0.25, 0.5]), 2)
        if refund_amount is not None:
            rdate = odate + timedelta(days=rng.randint(5, 40))
            reason = None if rdate < REASON_TRACKING_DATE else rng.choice(REFUND_REASONS)
            refunds.append((refund_id, oid, money(refund_amount), rdate, reason))
            refund_id += 1

    data["orders"] = orders
    data["order_items"] = items
    data["payments"] = payments
    data["refunds"] = refunds

    legacy = []
    for o in orders[:5_000]:
        legacy.append((o[0], o[1], o[2], money(float(o[5]) * rng.uniform(0.9, 1.1))))
    data["legacy_orders_v1"] = legacy
    return data


COLUMNS = {
    "regions": "region_id, name, country",
    "customers": "customer_id, first_name, last_name, email, region_id, segment, signup_date",
    "products": "product_id, name, category, price, is_active",
    "orders": "order_id, customer_id, order_date, status, channel, amount",
    "order_items": "order_item_id, order_id, product_id, quantity, unit_price",
    "payments": "payment_id, order_id, method, amount, paid_at",
    "refunds": "refund_id, order_id, amount, refunded_at, reason",
    "legacy_orders_v1": "id, cust, dt, total",
}
LOAD_ORDER = list(COLUMNS)


def load(dsn: str, data: dict[str, list[tuple]]) -> None:
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            "TRUNCATE " + ", ".join(f"analytics.{t}" for t in reversed(LOAD_ORDER)) + " CASCADE"
        )
        for table in LOAD_ORDER:
            rows = data[table]
            with cur.copy(f"COPY analytics.{table} ({COLUMNS[table]}) FROM STDIN") as cp:
                for row in rows:
                    cp.write_row(row)
            print(f"  {table:<18} {len(rows):>9,} rows")
        conn.commit()
        conn.autocommit = True
        cur.execute("ANALYZE")


def main() -> None:
    load_dotenv()
    dsn = os.environ.get("ADMIN_DSN", "postgresql://postgres:postgres@localhost:5433/analytics")
    t0 = time.time()
    print(f"Generating data (seed={SEED})...")
    data = generate(random.Random(SEED))
    print("Loading into Postgres...")
    load(dsn, data)
    total = sum(len(v) for v in data.values())
    print(f"Done: {total:,} rows in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
