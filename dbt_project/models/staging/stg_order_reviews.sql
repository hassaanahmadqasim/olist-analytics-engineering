with src as (
    select * from {{ source('bronze', 'order_reviews') }}
),

flagged as (
    select *, {{ reject_reason_order_reviews() }} as reject_reason
    from src
),

deduped as (
    select * from flagged
    where reject_reason is null
    qualify row_number() over (
        partition by review_id, order_id order by batch_id desc, ingested_at desc
    ) = 1
)

select
    review_id || '-' || order_id as review_key,
    review_id,
    order_id,
    cast(review_score as integer) as review_score,
    nullif(trim(review_comment_title), '') as review_comment_title,
    nullif(trim(review_comment_message), '') as review_comment_message,
    try_cast(review_creation_date as timestamp) as review_created_at,
    try_cast(review_answer_timestamp as timestamp) as review_answered_at,
    batch_id as _batch_id,
    ingested_at as _ingested_at
from deduped