with shopee as (
    select coalesce(try_strptime(order_date, '%d/%m/%Y'), try_cast(order_date as timestamp))::date as order_date,
        try_cast(replace(total_amount, '.', '') as bigint) as amount
    from {{ source('raw', 'shopee_orders') }} where status = 'COMPLETED'
),
tiki as (
    select cast(created_at as timestamp)::date as order_date, cast(grand_total as bigint) as amount
    from {{ source('raw', 'tiki_orders') }} where state = 'delivered'
),
web as (
    select cast(created_ts as timestamp)::date as order_date, cast(amount_vnd as bigint) as amount
    from {{ source('raw', 'website_orders') }} where status = 'paid'
),
all_orders as (select * from shopee union all select * from tiki union all select * from web)
select order_date, count(*) as order_count, sum(amount) as revenue_vnd from all_orders group by order_date
