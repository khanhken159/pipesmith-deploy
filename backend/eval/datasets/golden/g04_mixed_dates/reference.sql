select coalesce(try_strptime(order_date, '%d/%m/%Y'), try_cast(order_date as timestamp))::date as order_date,
    count(*) as order_count, sum(cast(total_amount as bigint)) as revenue_vnd
from {{ source('raw', 'shopee_orders') }} where status = 'COMPLETED' group by 1
