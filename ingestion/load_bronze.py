"""Load Olist CSVs into DuckDB bronze: raw as-is (all VARCHAR) + metadata columns.
Append-only. A batch_id is loaded once; re-runs skip it."""
import argparse
import re
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from config import RAW_DIR, SOURCES, WAREHOUSE_PATH


def sql_path(path: Path) -> str:
    return path.as_posix().replace("'", "''")


def scalar(con, sql: str, params=None):
    return con.execute(sql, params or []).fetchall()[0][0]


def table_exists(con, table: str) -> bool:
    return scalar(
        con,
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema = 'bronze' AND table_name = ?",
        [table],
    ) > 0


def load_batch(con, source_dir: Path, batch_id: str, verbose: bool = True) -> dict:
    ingested_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")  # UTC
    loaded = {}
    for file_name, table in SOURCES.items():
        path = source_dir / file_name
        if not path.exists():
            continue  # batches only contain the tables that changed

        exists = table_exists(con, table)
        if exists and scalar(
            con, f"SELECT count(*) FROM bronze.{table} WHERE batch_id = ?", [batch_id]
        ):
            if verbose:
                print(f"SKIP  {table}: batch {batch_id} already loaded")
            continue

        select = f"""
            SELECT *,
                   TIMESTAMP '{ingested_at}' AS ingested_at,
                   '{file_name}' AS source_name,
                   '{batch_id}' AS batch_id
            FROM read_csv('{sql_path(path)}', header = true, all_varchar = true, quote = '"', escape = '"')
        """
        if exists:
            con.execute(f"INSERT INTO bronze.{table} {select}")
        else:
            con.execute(f"CREATE TABLE bronze.{table} AS {select}")

        loaded[table] = scalar(
            con, f"SELECT count(*) FROM bronze.{table} WHERE batch_id = ?", [batch_id]
        )
        if verbose:
            print(f"OK    {table}: {loaded[table]:,} rows")
    return loaded


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
