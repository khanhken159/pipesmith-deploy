with all_orders as (
    select strptime(order_date, '%d/%m/%Y')::date as order_date, cast(replace(total_amount, '.', '') as bigint) as amount
    from {{ source('raw', 'shopee_orders') }} where status = 'COMPLETED'
    union all
    select cast(created_ts as timestamp)::date, cast(amount_vnd as bigint)
    from {{ source('raw', 'website_orders') }} where status = 'paid'
)
select order_date, count(*) as order_count, sum(amount) as revenue_vnd from all_orders group by order_date
