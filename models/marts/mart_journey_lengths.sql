-- Conversion rate by how many impressions a user saw inside the window.

select
    least(touches, 12)                                      as touches,
    touches >= 12                                           as is_capped,
    count(*)                                                as users,
    count(*) filter (where converted)                       as conversions,
    count(*) filter (where converted) / count(*)            as conversion_rate
from {{ ref('int_user_journeys') }}
group by 1, 2
order by 1
