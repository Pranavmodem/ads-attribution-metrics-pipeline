-- One row per model per channel: credit share, what that share implies in
-- conversions, revenue, and ROAS, and (on synthetic data) how far it is from the truth.
-- Every model splits the same pool: conversions with at least one impression in
-- the attribution window.

with attributable as (
    select count(*) as conversions, sum(revenue_attributed) as revenue_usd
    from {{ ref('attribution_touchpoints') }}
    where model = 'last_touch'
),

spend as (
    select channel, sum(cost_usd) as spend_usd, count(*) as impressions
    from {{ ref('stg_impressions') }}
    group by 1
),

credits as (
    select model, model_label, model_family, channel, credit
    from {{ ref('attribution_channel_credits') }}
    {% if var('synthetic_ground_truth') %}
    union all
    select 'ground_truth', 'Ground truth', 'truth', channel, credit
    from {{ ref('attribution_ground_truth') }}
    {% endif %}
)

select
    c.model,
    c.model_label,
    c.model_family,
    c.channel,
    c.credit,
    c.credit * a.conversions                                    as attributed_conversions,
    c.credit * a.revenue_usd                                    as attributed_revenue_usd,
    s.spend_usd,
    s.impressions,
    c.credit * a.revenue_usd / nullif(s.spend_usd, 0)           as roas,
    s.spend_usd / nullif(c.credit * a.conversions, 0)           as cpa_usd,
    {% if var('synthetic_ground_truth') %}
    g.credit                                                    as true_credit,
    (c.credit - g.credit) * 100                                 as error_pp
    {% else %}
    null::double                                                as true_credit,
    null::double                                                as error_pp
    {% endif %}
from credits c
cross join attributable a
left join spend s using (channel)
{% if var('synthetic_ground_truth') %}
left join {{ ref('attribution_ground_truth') }} g using (channel)
{% endif %}
