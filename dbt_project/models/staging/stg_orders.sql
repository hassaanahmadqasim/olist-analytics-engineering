with src as (
    select * from {{ source('bronze', 'orders') }}
),

flagged as (
    select *, {{ reject_reason_orders() }} as reject_reason
    from src
),

deduped as (
    select * from flagged
    where reject_reason is null
    qualify row_number() over (
        partition by order_id order by batch_id desc, ingested_at desc
    ) = 1
),

typed as (
    select
        order_id,
        customer_id,
        order_status,
        try_cast(order_purchase_timestamp as timestamp) as purchased_at,
        try_cast(order_approved_at as timestamp) as approved_at,
        try_cast(order_delivered_carrier_date as timestamp) as shipped_at,
        try_cast(order_delivered_customer_date as timestamp) as delivered_at,
        try_cast(order_estimated_delivery_date as timestamp) as estimated_delivery_at,
        batch_id as _batch_id,
        ingested_at as _ingested_at
    from deduped
)

select
    *,
    (purchased_at >= cast('{{ var("start_date") }}' as timestamp)
        and purchased_at < cast('{{ var("end_date_exclusive") }}' as timestamp)) as is_in_scope,
    (order_status = 'delivered' and delivered_at is null) as is_delivery_timestamp_missing
from typed