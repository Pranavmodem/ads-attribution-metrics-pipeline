-- No impression gets credit for a conversion that came before it, or after the window closed.
select *
from {{ ref('attribution_touchpoints') }}
where impression_ts > conversion_ts
   or impression_ts < conversion_ts - to_days({{ var('attribution_window_days') }})
