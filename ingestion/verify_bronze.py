"""Reconcile bronze (all batches) against raw CSVs + the injected manifest."""
import csv
import sys

import duckdb

from config import BATCH_DIR, RAW_DIR, SOURCES, WAREHOUSE_PATH

con = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)


def scalar(sql):
    return con.execute(sql).fetchall()[0][0]


extra = {}
with (BATCH_DIR / "injected_manifest.csv").open(newline="", encoding="utf-8") as fh:
    for row in csv.DictReader(fh):
        extra[row["table_name"]] = extra.get(row["table_name"], 0) + 1

failed = False
print(f"{'table':30}{'raw':>10}{'extra':>8}{'expected':>10}{'bronze':>10}  status")
for file_name, table in SOURCES.items():
    raw_rows = scalar(
        f"SELECT count(*) FROM read_csv('{(RAW_DIR / file_name).as_posix()}', "
        "header=true, all_varchar=true)"
    )
    expected = raw_rows + extra.get(table, 0)
    bronze_rows = scalar(f"SELECT count(*) FROM bronze.{table}")
    ok = expected == bronze_rows
    failed |= not ok
    print(f"{table:30}{raw_rows:>10,}{extra.get(table, 0):>8,}{expected:>10,}{bronze_rows:>10,}  "
          f"{'OK' if ok else 'MISMATCH'}")

raw_orders = (RAW_DIR / "olist_orders_dataset.csv").as_posix()
mismatch = scalar(f"""
    WITH latest AS (
        SELECT * FROM bronze.orders
        WHERE order_id IS NOT NULL AND order_id NOT LIKE 'INJ-%'
        QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY batch_id DESC) = 1)
    SELECT count(*) FROM latest l
    FULL JOIN read_csv('{raw_orders}', header=true, all_varchar=true) r USING (order_id)
    WHERE l.order_status IS DISTINCT FROM r.order_status
       OR l.order_delivered_customer_date IS DISTINCT FROM r.order_delivered_customer_date""")
failed |= mismatch != 0
print(f"\nLatest-batch orders vs raw: {mismatch} mismatches {'OK' if mismatch == 0 else 'FAIL'}")
print(f"Batches in bronze: {scalar('SELECT count(DISTINCT batch_id) FROM bronze.orders')}")

print("\nMetadata sample:")
con.cursor().sql(
    "SELECT ingested_at, source_name, batch_id FROM bronze.orders ORDER BY batch_id DESC LIMIT 3"
).show()
sys.exit(1 if failed else 0)