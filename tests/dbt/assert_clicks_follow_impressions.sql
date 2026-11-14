-- A click cannot happen before the impression it came from, or belong to another user.
select k.click_id
from {{ ref('stg_clicks') }} k
join {{ ref('stg_impressions') }} i using (impression_id)
where k.click_ts < i.impression_ts
   or k.user_id != i.user_id
