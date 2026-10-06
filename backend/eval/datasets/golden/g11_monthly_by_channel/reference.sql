select date_trunc('month', cast(order_date as date))::date as month, channel, count(*) as order_count,
    sum(cast(amount_vnd as bigint)) as revenue_vnd
from {{ source('raw', 'orders') }} where status = 'completed' group by 1, 2
