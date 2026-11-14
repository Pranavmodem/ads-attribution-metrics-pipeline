-- Under every model, campaign-level conversions add up to the conversions that were attributed.
with credited as (
    select model, count(distinct conversion_id) as conversions
    from {{ ref('attribution_touchpoints') }}
    group by 1
),

campaigns as (
    select model, sum(conversions) as conversions
    from {{ ref('mart_campaign_performance') }}
    group by 1
)

select *
from credited
join campaigns using (model)
where abs(credited.conversions - campaigns.conversions) > 1e-6
