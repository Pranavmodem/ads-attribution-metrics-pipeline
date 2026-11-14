-- Daily and campaign marts must add up to the same spend as the impressions they came from.
with totals as (
    select
        (select sum(cost_usd) from {{ ref('stg_impressions') }})                                    as impressions,
        (select sum(spend_usd) from {{ ref('mart_daily_performance') }})                            as daily,
        (select sum(spend_usd) from {{ ref('mart_campaign_performance') }} where model = 'last_touch') as campaigns
)
select *
from totals
where abs(impressions - daily) > 0.01
   or abs(impressions - campaigns) > 0.01
