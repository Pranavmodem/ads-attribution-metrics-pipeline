-- One row per day: delivery, spend, and outcomes. Conversions count on the day they happened.

with delivery as (
    select impression_date as date, count(*) as impressions, count(distinct user_id) as users_reached,
           sum(cost_usd) as spend_usd
    from {{ ref('stg_impressions') }}
    group by 1
),

clicks as (
    select click_date as date, count(*) as clicks
    from {{ ref('stg_clicks') }}
    group by 1
),

outcomes as (
    select conversion_date as date, count(*) as conversions, sum(revenue_usd) as revenue_usd,
           count(*) filter (where is_late_arrival) as late_conversions
    from {{ ref('stg_conversions') }}
    group by 1
)

select
    d.date,
    d.impressions,
    d.users_reached,
    coalesce(c.clicks, 0)                                   as clicks,
    d.spend_usd,
    coalesce(o.conversions, 0)                              as conversions,
    coalesce(o.revenue_usd, 0)                              as revenue_usd,
    coalesce(o.late_conversions, 0)                         as late_conversions,
    coalesce(c.clicks, 0) / d.impressions                   as ctr,
    d.spend_usd / d.impressions * 1000                      as cpm_usd,
    coalesce(o.revenue_usd, 0) / nullif(d.spend_usd, 0)     as roas
from delivery d
left join clicks c using (date)
left join outcomes o using (date)
order by d.date
