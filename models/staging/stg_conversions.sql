-- models/staging/stg_conversions.sql
-- Staging: clean and type-cast raw conversion events.
-- Tags late-arriving conversions based on attribution window.

with source as (
    select * from {{ source('ads_raw', 'conversions') }}
),

deduplicated as (
    select
        *,
        row_number() over (
            partition by conversion_id
            order by timestamp asc
        ) as _row_num
    from source
),

cleaned as (
    select
        cast(conversion_id as string)               as conversion_id,
        cast(timestamp as timestamp)                 as conversion_timestamp,
        cast(user_id as string)                      as user_id,
        lower(trim(conversion_type))                 as conversion_type,
        cast(revenue_usd as float64)                 as revenue_usd,
        cast(attributed_impression_id as string)     as attributed_impression_id,
        date(timestamp)                              as conversion_date,
        -- Flag late arrivals: conversion > 30 days after impression
        case
            when date_diff(date(timestamp), current_date(), day) > 30
            then true else false
        end as is_late_arrival
    from deduplicated
    where _row_num = 1
      and conversion_id is not null
      and timestamp is not null
)

select * from cleaned
