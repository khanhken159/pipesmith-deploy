with latest as (
    select customer_id, email, city from {{ source('raw', 'customers') }}
    qualify row_number() over (partition by customer_id order by cast(updated_at as date) desc) = 1
),
done as (select customer_id, count(*) as n from {{ source('raw', 'orders') }} where status = 'completed' group by 1)
select l.customer_id, l.email, l.city, coalesce(d.n, 0) as completed_orders
from latest l left join done d on l.customer_id = d.customer_id
