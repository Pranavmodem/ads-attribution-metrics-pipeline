-- Every heuristic model hands out exactly one conversion's worth of credit per conversion.
select model, conversion_id, sum(credit) as total_credit
from {{ ref('attribution_touchpoints') }}
group by 1, 2
having abs(sum(credit) - 1) > 1e-9
