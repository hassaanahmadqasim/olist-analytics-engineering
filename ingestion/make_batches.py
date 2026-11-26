"""Slice raw Olist CSVs into a baseline batch + weekly batches by order purchase date."""
import shutil

import duckdb

from config import BATCH_DIR, RAW_DIR, SOURCES

BASELINE_ID = "batch_000_baseline"
START = "2017-01-01"  # orders before this date go to the baseline batch
FILES = {table: file for file, table in SOURCES.items()}
REFERENCE = ["products", "sellers", "geolocation", "product_category_translation"]
BY_ORDER = ["orders", "order_items", "order_payments", "order_reviews"]


def main() -> None:
    if BATCH_DIR.exists():
        shutil.rmtree(BATCH_DIR)
    BATCH_DIR.mkdir(parents=True)

    con = duckdb.connect()
    for table, file in FILES.items():
        path = (RAW_DIR / file).as_posix()
        con.execute(
            f"CREATE VIEW raw_{table} AS "
            f"SELECT * FROM read_csv('{path}', header=true, all_varchar=true)"
        )

    purchase_date = "CAST(CAST(order_purchase_timestamp AS TIMESTAMP) AS DATE)"
    con.execute(f"""
        CREATE TABLE order_week AS
        SELECT order_id, customer_id,
               CASE WHEN {purchase_date} < DATE '{START}' THEN NULL
                    ELSE CAST(DATE '{START}' + to_days(CAST(
                         7 * (datediff('day', DATE '{START}', {purchase_date}) // 7) AS INTEGER)) AS DATE)
               END AS week_start
        FROM raw_orders""")
    con.execute("""
        CREATE TABLE weeks AS
        SELECT week_start,
               'batch_' || lpad(CAST(row_number() OVER (ORDER BY week_start) AS VARCHAR), 3, '0')
               || '_' || CAST(week_start AS VARCHAR) AS batch_id
        FROM (SELECT DISTINCT week_start FROM order_week WHERE week_start IS NOT NULL)""")
    con.execute(f"""
        CREATE TABLE order_batch AS
        SELECT o.order_id, o.customer_id, COALESCE(w.batch_id, '{BASELINE_ID}') AS batch_id
        FROM order_week o LEFT JOIN weeks w USING (week_start)""")

    batches = [r[0] for r in con.execute(
        "SELECT DISTINCT batch_id FROM order_batch ORDER BY 1").fetchall()]
    totals = {t: 0 for t in FILES}

    for b in batches:
        d = BATCH_DIR / b
        d.mkdir()
        queries = {}
        for t in BY_ORDER:
            queries[t] = (f"SELECT t.* FROM raw_{t} t JOIN order_batch ob USING (order_id) "
                          f"WHERE ob.batch_id = '{b}'")
        queries["customers"] = ("SELECT t.* FROM raw_customers t JOIN order_batch ob "
                                f"USING (customer_id) WHERE ob.batch_id = '{b}'")
        if b == BASELINE_ID:
            for t in REFERENCE:
                queries[t] = f"SELECT * FROM raw_{t}"
        for table, q in queries.items():
            n = con.execute(f"SELECT count(*) FROM ({q})").fetchall()[0][0]
            if n == 0:
                continue
            out = (d / FILES[table]).as_posix()
            con.execute(f"COPY ({q}) TO '{out}' (HEADER, DELIMITER ',')")
            totals[table] += n

    print(f"{len(batches)} batches written to {BATCH_DIR}\n")
    print(f"{'table':32}{'raw_rows':>12}{'in_batches':>12}  status")
    ok = True
    for table in FILES:
        raw_n = con.execute(f"SELECT count(*) FROM raw_{table}").fetchall()[0][0]
        good = raw_n == totals[table]
        ok &= good
        print(f"{table:32}{raw_n:>12,}{totals[table]:>12,}  {'OK' if good else 'MISMATCH'}")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()