"""Check bronze row counts match the source CSVs for a batch."""
import argparse
import sys

import duckdb

from config import RAW_DIR, SOURCES, WAREHOUSE_PATH

parser = argparse.ArgumentParser()
parser.add_argument("--batch-id", default="batch_000_baseline")
args = parser.parse_args()

con = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)
failed = False
print(f"{'table':32}{'csv_rows':>12}{'bronze_rows':>14}  status")
for file_name, table in SOURCES.items():
    csv_path = (RAW_DIR / file_name).as_posix()
    csv_rows = con.execute(
        f"SELECT count(*) FROM read_csv('{csv_path}', header=true, all_varchar=true)"
    ).fetchone()[0]
    bronze_rows = con.execute(
        f"SELECT count(*) FROM bronze.{table} WHERE batch_id = ?", [args.batch_id]
    ).fetchone()[0]
    ok = csv_rows == bronze_rows
    failed |= not ok
    print(f"{table:32}{csv_rows:>12,}{bronze_rows:>14,}  {'OK' if ok else 'MISMATCH'}")

print("\nMetadata sample:")
con.cursor().sql("SELECT ingested_at, source_name, batch_id FROM bronze.orders LIMIT 3").show()
sys.exit(1 if failed else 0)
