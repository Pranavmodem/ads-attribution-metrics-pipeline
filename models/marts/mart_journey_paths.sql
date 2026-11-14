-- Channel paths ranked by how many users followed them, with their conversion rate.

select
    path,
    len(string_split(path, ' > '))                          as steps,
    count(*)                                                as users,
    count(*) filter (where converted)                       as conversions,
    count(*) filter (where converted) / count(*)            as conversion_rate,
    avg(touches)                                            as avg_touches,
    median(days_to_convert)                                 as median_days_to_convert
from {{ ref('int_user_journeys') }}
group by path
