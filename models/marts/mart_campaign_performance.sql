-- One row per campaign per heuristic attribution model: delivery, cost, and the
-- conversions and revenue that model credits to the campaign.

with delivery as (
    select campaign_id, count(*) as impressions, count(distinct user_id) as users_reached,
           sum(cost_usd) as spend_usd
    from {{ ref('stg_impressions') }}
    group by 1
),

clicks as (
    select campaign_id, count(*) as clicks
    from {{ ref('stg_clicks') }}
    group by 1
),

credited as (
    select model, campaign_id, sum(credit) as conversions, sum(revenue_attributed) as revenue_usd
    from {{ ref('attribution_touchpoints') }}
    group by 1, 2
),

models as (
    select distinct model from {{ ref('attribution_touchpoints') }}
)

select
    m.model,
    c.campaign_id,
    c.campaign_name,
    c.advertiser_name,
    c.channel,
    c.status,
    d.impressions,
    d.users_reached,
    coalesce(k.clicks, 0)                                           as clicks,
    d.spend_usd,
    coalesce(cr.conversions, 0)                                     as conversions,
    coalesce(cr.revenue_usd, 0)                                     as revenue_usd,
    coalesce(k.clicks, 0) / d.impressions                           as ctr,
    d.spend_usd / d.impressions * 1000                              as cpm_usd,
    coalesce(cr.conversions, 0) / d.users_reached                   as conversion_rate,
    coalesce(cr.revenue_usd, 0) / nullif(d.spend_usd, 0)            as roas,
    d.spend_usd / nullif(cr.conversions, 0)                         as cpa_usd
from {{ ref('stg_campaigns') }} c
cross join models m
join delivery d using (campaign_id)
left join clicks k using (campaign_id)
left join credited cr on cr.model = m.model and cr.campaign_id = c.campaign_id
