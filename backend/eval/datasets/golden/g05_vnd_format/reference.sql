select cast(order_date as date) as order_date, count(*) as order_count,
    sum(cast(replace(total_amount, '.', '') as bigint)) as revenue_vnd
from {{ source('raw', 'shopee_orders') }} where status = 'COMPLETED' group by 1
