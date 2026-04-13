-- models/marts/mart_campaign_metrics.sql
-- Final business metrics mart: one row per campaign per day.
-- This is the primary table backing the self-service dashboard.

with base as (
    select * from {{ ref('int_impression_conversions') }}
),

campaign_daily as (
    select
        campaign_id,
        impression_date                             as metric_date,

        -- Volume metrics
        count(distinct impression_id)               as total_impressions,
        count(distinct user_id)                     as unique_users,
        count(distinct case when has_conversion then conversion_id end)
                                                    as total_conversions,

        -- Revenue & spend
        sum(bid_price_usd)                          as total_spend_usd,
        sum(case when has_conversion then revenue_usd else 0 end)
                                                    as total_revenue_attributed_usd,

        -- Device breakdown
        count(distinct case when device_type = 'ctv' then impression_id end)
                                                    as ctv_impressions,
        count(distinct case when device_type = 'mobile' then impression_id end)
                                                    as mobile_impressions,

        -- Geo breakdown
        count(distinct case when geo_country = 'US' then impression_id end)
                                                    as us_impressions,

        -- Conversion timing
        avg(case when has_conversion then hours_to_conversion end)
                                                    as avg_hours_to_conversion,

        -- Late arrival tracking
        count(distinct case when is_late_arrival then conversion_id end)
                                                    as late_arrival_conversions

    from base
    group by 1, 2
),

with_derived_metrics as (
    select
        *,
        -- CPM: cost per thousand impressions
        safe_divide(total_spend_usd, total_impressions) * 1000
            as cpm,

        -- Conversion rate: conversions / impressions
        safe_divide(total_conversions, total_impressions)
            as conversion_rate,

        -- ROAS: return on ad spend
        safe_divide(total_revenue_attributed_usd, total_spend_usd)
            as roas,

        -- CPA: cost per acquisition
        safe_divide(total_spend_usd, total_conversions)
            as cost_per_acquisition,

        -- Avg frequency: impressions per unique user
        safe_divide(total_impressions, unique_users)
            as avg_frequency,

        -- CTV share: % of impressions on connected TV
        safe_divide(ctv_impressions, total_impressions)
            as ctv_impression_share,

        -- US share
        safe_divide(us_impressions, total_impressions)
            as us_impression_share

    from campaign_daily
)

select * from with_derived_metrics
order by metric_date desc, total_impressions desc
