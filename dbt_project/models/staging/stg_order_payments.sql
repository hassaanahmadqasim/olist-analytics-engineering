with src as (
    select * from {{ source('bronze', 'order_payments') }}
),

flagged as (
    select *, {{ reject_reason_order_payments() }} as reject_reason
    from src
),

deduped as (
    select * from flagged
    where reject_reason is null
    qualify row_number() over (
        partition by order_id, payment_sequential order by batch_id desc, ingested_at desc
    ) = 1
)

select
    order_id || '-' || payment_sequential as payment_key,
    order_id,
    cast(payment_sequential as integer) as payment_sequential,
    payment_type,
    cast(payment_installments as integer) as payment_installments,
    cast(payment_value as decimal(12,2)) as payment_value,
    batch_id as _batch_id,
    ingested_at as _ingested_at
from deduped