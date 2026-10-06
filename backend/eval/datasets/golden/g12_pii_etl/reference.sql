select city, count(*) as customer_count from {{ source('raw', 'customers') }} group by city
