"""Inject late-arriving updates and bad rows into the batches (seeded, reproducible).
Writes data/batches/injected_manifest.csv. Run once, right after make_batches.py."""
import csv
import random
import sys

from config import BATCH_DIR, SOURCES

SEED = 42
N_LATE = 300
N_BAD = 5
BASELINE_ID = "batch_000_baseline"
FILES = {table: file for file, table in SOURCES.items()}
MANIFEST = BATCH_DIR / "injected_manifest.csv"
FIELDS = ["injection_id", "kind", "batch_id", "table_name", "defect_type", "key_detail"]
store = {}


def get(batch, table):
    key = (batch, table)
    if key not in store:
        path = BATCH_DIR / batch / FILES[table]
        if not path.exists():
            store[key] = ([], [])
        else:
            with path.open(newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                store[key] = (reader.fieldnames, list(reader))
    return store[key]


def main() -> None:
    if MANIFEST.exists():
        sys.exit("Already injected. Run make_batches.py first to reset.")
    rng = random.Random(SEED)
    weekly = sorted(p.name for p in BATCH_DIR.iterdir() if p.is_dir() and p.name != BASELINE_ID)
    manifest = []

    # 1) Late-arriving updates: stale copy in home batch, true row re-delivered 2 batches later
    cands = [
        (i, r["order_id"])
        for i, b in enumerate(weekly[:-2])
        for r in get(b, "orders")[1]
        if r["order_status"] == "delivered" and r["order_delivered_customer_date"]
    ]
    for k, (i, oid) in enumerate(sorted(rng.sample(cands, N_LATE)), start=1):
        home, final = weekly[i], weekly[i + 2]
        row = next(r for r in get(home, "orders")[1] if r["order_id"] == oid)
        get(final, "orders")[1].append(dict(row))  # true version arrives later
        row["order_status"] = "shipped"  # stale version
        row["order_delivered_customer_date"] = ""
        manifest.append({
            "injection_id": f"UPD-{k:04d}", "kind": "late_update", "batch_id": home,
            "table_name": "orders", "defect_type": "stale_status",
            "key_detail": f"order_id={oid};final_batch={final}",
        })

    # 2) Bad rows
    tables = ("orders", "order_items", "order_payments", "order_reviews")
    eligible = [b for b in weekly if all(len(get(b, t)[1]) >= 20 for t in tables)]
    counter = [0]

    def new_id():
        counter[0] += 1
        return f"INJ-{counter[0]:04d}"

    def log(inj, batch, table, defect, key):
        manifest.append({
            "injection_id": inj, "kind": "bad_row", "batch_id": batch,
            "table_name": table, "defect_type": defect, "key_detail": key,
        })

    for _ in range(N_BAD):
        b = rng.choice(eligible)
        rows = get(b, "orders")[1]
        inj = new_id()
        r = dict(rng.choice(rows)); r["order_id"] = ""; r["customer_id"] = inj
        rows.append(r)
        log(inj, b, "orders", "null_order_id", f"customer_id={inj}")

        b = rng.choice(eligible)
        rows = get(b, "orders")[1]
        inj = new_id()
        r = dict(rng.choice(rows)); r["order_id"] = inj; r["order_status"] = "teleported"
        rows.append(r)
        log(inj, b, "orders", "invalid_status", f"order_id={inj}")

        b = rng.choice(eligible)
        rows = get(b, "order_items")[1]
        r = dict(rng.choice(rows)); r["order_item_id"] = "9"
        r["price"] = f"-{abs(float(r['price'])):.2f}"
        rows.append(r)
        log(new_id(), b, "order_items", "negative_amount",
            f"order_id={r['order_id']};order_item_id=9")

        b = rng.choice(eligible)
        rows = get(b, "order_payments")[1]
        r = dict(rng.choice(rows)); r["payment_sequential"] = "9"
        r["payment_value"] = f"-{abs(float(r['payment_value'])):.2f}"
        rows.append(r)
        log(new_id(), b, "order_payments", "negative_amount",
            f"order_id={r['order_id']};payment_sequential=9")

        b = rng.choice(eligible)
        rows = get(b, "order_reviews")[1]
        inj = new_id()
        r = dict(rng.choice(rows)); r["review_id"] = inj; r["review_score"] = "9"
        rows.append(r)
        log(inj, b, "order_reviews", "invalid_score", f"review_id={inj}")

    # 3) Write back
    for (batch, table), (fields, rows) in store.items():
        if not fields:
            continue
        path = BATCH_DIR / batch / FILES[table]
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    with MANIFEST.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(manifest)

    late = sum(m["kind"] == "late_update" for m in manifest)
    print(f"late updates: {late}, bad rows: {len(manifest) - late}")
    print(f"manifest: {MANIFEST}")


if __name__ == "__main__":
    main()