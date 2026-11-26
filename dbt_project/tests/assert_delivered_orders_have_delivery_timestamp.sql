{{ config(severity='warn') }}
-- Olist defect: some delivered orders have no delivery timestamp.
-- They stay in silver (flagged) and are excluded from delivery metrics in gold.
select order_id, order_status, purchased_at, delivered_at
from {{ ref('stg_orders') }}
where is_delivery_timestamp_missing