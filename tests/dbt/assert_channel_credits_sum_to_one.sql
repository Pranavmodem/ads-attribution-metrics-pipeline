-- Each model's channel shares form a full split of the conversions.
select model, sum(credit) as total_credit
from {{ ref('attribution_channel_credits') }}
group by 1
having abs(sum(credit) - 1) > 1e-9
