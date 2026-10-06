with dedup as (
    select distinct order_id, strptime(order_date, '%d/%m/%Y')::date as order_date,
        cast(replace(total_amount, '.', '') as bigint) as amount
    from {{ source('raw', 'shopee_orders') }} where status = 'COMPLETED'
)
select order_date, count(*) as order_count, sum(amount) as revenue_vnd from dedup group by order_date
