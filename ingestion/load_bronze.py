"""Load Olist CSVs into DuckDB bronze: raw as-is (all VARCHAR) + metadata columns."""
import argparse
import re
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from config import RAW_DIR, SOURCES, WAREHOUSE_PATH


def sql_path(path: Path) -> str:
    return path.as_posix().replace("'", "''")


def table_exists(con, table: str) -> bool:
    return con.execute(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema = 'bronze' AND table_name = ?",
        [table],
    ).fetchone()[0] > 0


def load_batch(con, source_dir: Path, batch_id: str) -> None:
    ingested_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")  # UTC
    for file_name, table in SOURCES.items():
        path = source_dir / file_name
        if not path.exists():
            raise FileNotFoundError(path)

        exists = table_exists(con, table)
        if exists:
            already = con.execute(
                f"SELECT count(*) FROM bronze.{table} WHERE batch_id = ?", [batch_id]
            ).fetchone()[0]
            if already:
                print(f"SKIP  {table}: batch {batch_id} already loaded")
                continue

        select = f"""
            SELECT *,
                   TIMESTAMP '{ingested_at}' AS ingested_at,
                   '{file_name}' AS source_name,
                   '{batch_id}' AS batch_id
            FROM read_csv('{sql_path(path)}', header = true, all_varchar = true)
        """
        if exists:
            con.execute(f"INSERT INTO bronze.{table} {select}")
        else:
            con.execute(f"CREATE TABLE bronze.{table} AS {select}")

        n = con.execute(
            f"SELECT count(*) FROM bronze.{table} WHERE batch_id = ?", [batch_id]
        ).fetchone()[0]
        print(f"OK    {table}: {n:,} rows")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--batch-id", default="batch_000_baseline")
    parser.add_argument("--reset", action="store_true", help="drop bronze schema first")
    args = parser.parse_args()

    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.batch_id):
        parser.error("batch-id: letters, digits, _ and - only")

    WAREHOUSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE_PATH))
    if args.reset:
        con.execute("DROP SCHEMA IF EXISTS bronze CASCADE")
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
    load_batch(con, args.source_dir, args.batch_id)
    con.close()


if __name__ == "__main__":
    main()