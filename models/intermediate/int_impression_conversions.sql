-- models/intermediate/int_impression_conversions.sql
-- Joins impressions with their attributed conversions.
-- Forms the base for all attribution metric calculations.

with impressions as (
    select * from {{ ref('stg_impressions') }}
),

conversions as (
    select * from {{ ref('stg_conversions') }}
),

joined as (
    select
        i.impression_id,
        i.impression_timestamp,
        i.campaign_id,
        i.placement_id,
        i.creative_id,
        i.user_id,
        i.user_segment_id,
        i.device_type,
        i.geo_country,
        i.bid_price_usd,
        i.impression_date,

        c.conversion_id,
        c.conversion_timestamp,
        c.conversion_type,
        c.revenue_usd,
        c.is_late_arrival,

        -- Time between impression and conversion
        timestamp_diff(c.conversion_timestamp, i.impression_timestamp, hour)
            as hours_to_conversion,

        -- Attribution flag
        case when c.conversion_id is not null then true else false end
            as has_conversion

    from impressions i
    left join conversions c
        on i.impression_id = c.attributed_impression_id
)

select * from joined
