-- models/staging/stg_impressions.sql
-- Staging: clean, type-cast, and deduplicate raw ad impressions.
-- Deduplication uses impression_id as the natural key.

with source as (
    select * from {{ source('ads_raw', 'impressions') }}
),

deduplicated as (
    select
        *,
        row_number() over (
            partition by impression_id
            order by timestamp asc
        ) as _row_num
    from source
),

cleaned as (
    select
        cast(impression_id as string)       as impression_id,
        cast(timestamp as timestamp)        as impression_timestamp,
        cast(campaign_id as string)         as campaign_id,
        cast(placement_id as string)        as placement_id,
        cast(creative_id as string)         as creative_id,
        cast(user_id as string)             as user_id,
        cast(user_segment_id as string)     as user_segment_id,
        lower(trim(device_type))            as device_type,
        upper(trim(geo_country))            as geo_country,
        cast(bid_price_usd as float64)      as bid_price_usd,
        date(timestamp)                     as impression_date
    from deduplicated
    where _row_num = 1
      and impression_id is not null
      and timestamp is not null
)

select * from cleaned
