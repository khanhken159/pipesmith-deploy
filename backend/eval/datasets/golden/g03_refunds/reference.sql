select cast(created_ts as timestamp)::date as order_date, count(*) as order_count,
    sum(cast(amount_vnd as bigint)) as revenue_vnd
from {{ source('raw', 'website_orders') }} where status = 'paid' group by 1
