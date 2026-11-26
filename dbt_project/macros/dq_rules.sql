{# Reject rules, defined once. Used by stg_ models (to drop) and quarantine (to keep). #}
{# Reason names match defect_type in injected_manifest.csv #}

{% macro sql_list(values) %}
{%- for v in values -%}'{{ v }}'{{ ", " if not loop.last }}{%- endfor -%}
{% endmacro %}

{% macro reject_reason_orders() %}
case
    when nullif(trim(order_id), '') is null then 'null_order_id'
    when order_status is null
         or order_status not in ({{ sql_list(var('valid_order_statuses')) }}) then 'invalid_status'
    when try_cast(order_purchase_timestamp as timestamp) is null then 'invalid_purchase_timestamp'
end
{% endmacro %}

{% macro reject_reason_order_items() %}
case
    when nullif(trim(order_id), '') is null then 'null_order_id'
    when try_cast(price as decimal(12,2)) is null
         or try_cast(freight_value as decimal(12,2)) is null then 'invalid_amount'
    when try_cast(price as decimal(12,2)) < 0
         or try_cast(freight_value as decimal(12,2)) < 0 then 'negative_amount'
end
{% endmacro %}

{% macro reject_reason_order_payments() %}
case
    when nullif(trim(order_id), '') is null then 'null_order_id'
    when try_cast(payment_value as decimal(12,2)) is null then 'invalid_amount'
    when try_cast(payment_value as decimal(12,2)) < 0 then 'negative_amount'
end
{% endmacro %}

{% macro reject_reason_order_reviews() %}
case
    when nullif(trim(order_id), '') is null then 'null_order_id'
    when nullif(trim(review_id), '') is null then 'null_review_id'
    when coalesce(try_cast(review_score as integer) not between 1 and 5, true) then 'invalid_score'
end
{% endmacro %}