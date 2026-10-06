select cast(created_ts as timestamp)::date as order_date, count(*) as order_count,
    coalesce(sum(try_cast(amount_vnd as bigint)), 0) as revenue_vnd
from {{ source('raw', 'website_orders') }} where status = 'paid' group by 1
