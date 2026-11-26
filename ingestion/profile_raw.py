"""Confirm the known Olist data traps. Output feeds the README."""
import duckdb

from config import WAREHOUSE_PATH

con = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)

CHECKS = {
    "Order status counts": """
        SELECT order_status, count(*) AS n FROM bronze.orders GROUP BY 1 ORDER BY 2 DESC""",
    "Purchase date range": """
        SELECT min(order_purchase_timestamp) AS first_order,
               max(order_purchase_timestamp) AS last_order FROM bronze.orders""",
    "Orders per month": """
        SELECT substr(order_purchase_timestamp, 1, 7) AS month, count(*) AS n
        FROM bronze.orders GROUP BY 1 ORDER BY 1""",
    "Delivered with null delivery date": """
        SELECT count(*) AS n FROM bronze.orders
        WHERE order_status = 'delivered' AND order_delivered_customer_date IS NULL""",
    "Orders with no items": """
        SELECT count(*) AS n FROM bronze.orders o
        WHERE NOT EXISTS (SELECT 1 FROM bronze.order_items i WHERE i.order_id = o.order_id)""",
    "Orders with multiple payment rows": """
        SELECT count(*) AS n FROM (
            SELECT order_id FROM bronze.order_payments GROUP BY 1 HAVING count(*) > 1)""",
    "Duplicate review_id": """
        SELECT count(*) AS n FROM (
            SELECT review_id FROM bronze.order_reviews GROUP BY 1 HAVING count(*) > 1)""",
    "Orders with multiple reviews": """
        SELECT count(*) AS n FROM (
            SELECT order_id FROM bronze.order_reviews GROUP BY 1 HAVING count(*) > 1)""",
    "Geolocation rows vs distinct zip prefixes": """
        SELECT count(*) AS total_rows,
               count(DISTINCT geolocation_zip_code_prefix) AS prefixes FROM bronze.geolocation""",
    "Products with null category": """
        SELECT count(*) AS n FROM bronze.products WHERE product_category_name IS NULL""",
    "Categories missing from translation": """
        SELECT DISTINCT product_category_name FROM bronze.products p
        WHERE product_category_name IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM bronze.product_category_translation t
            WHERE t.product_category_name = p.product_category_name)""",
    "customer_id vs customer_unique_id": """
        SELECT count(*) AS customer_ids,
               count(DISTINCT customer_unique_id) AS unique_customers FROM bronze.customers""",
}

for title, query in CHECKS.items():
    print(f"\n=== {title} ===")
    con.sql(query).show()