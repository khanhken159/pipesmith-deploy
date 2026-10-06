with o as (
    select order_id, cast(order_date as date) as order_date, cast(total_vnd as bigint) as total_vnd
    from {{ source('raw', 'orders') }} where status = 'completed'
),
qty as (select order_id, sum(cast(qty as bigint)) as items from {{ source('raw', 'order_items') }} group by order_id)
select o.order_date, count(*) as order_count, sum(o.total_vnd) as revenue_vnd, sum(coalesce(qty.items, 0)) as items_sold
from o left join qty on o.order_id = qty.order_id group by o.order_date
