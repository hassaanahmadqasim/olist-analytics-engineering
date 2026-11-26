"""Rebuild bronze from every batch folder, in batch order."""
import duckdb

from config import BATCH_DIR, WAREHOUSE_PATH
from load_bronze import load_batch


def main() -> None:
    batches = sorted(p for p in BATCH_DIR.iterdir() if p.is_dir())
    WAREHOUSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE_PATH))
    con.execute("DROP SCHEMA IF EXISTS bronze CASCADE")
    con.execute("CREATE SCHEMA bronze")
    for d in batches:
        loaded = load_batch(con, d, d.name, verbose=False)
        print(f"{d.name:28} orders={loaded.get('orders', 0):>6,}  tables={len(loaded)}")
    con.close()
    print(f"\n{len(batches)} batches loaded into {WAREHOUSE_PATH}")


if __name__ == "__main__":
    main()