with src as (
    select * from {{ source('bronze', 'order_items') }}
),

flagged as (
    select *, {{ reject_reason_order_items() }} as reject_reason
    from src
),

deduped as (
    select * from flagged
    where reject_reason is null
    qualify row_number() over (
        partition by order_id, order_item_id order by batch_id desc, ingested_at desc
    ) = 1
)

select
    order_id || '-' || order_item_id as order_item_key,
    order_id,
    cast(order_item_id as integer) as order_item_id,
    product_id,
    seller_id,
    try_cast(shipping_limit_date as timestamp) as shipping_limit_at,
    cast(price as decimal(12,2)) as price,
    cast(freight_value as decimal(12,2)) as freight_value,
    batch_id as _batch_id,
    ingested_at as _ingested_at
from deduped