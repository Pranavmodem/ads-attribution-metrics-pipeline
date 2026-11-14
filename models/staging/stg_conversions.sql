-- One row per conversion. Upstream re-sends some events, and a re-send can land
-- in a later partition, so deduplication keeps the first copy received.

select
    conversion_id,
    cast("timestamp" as timestamp)                              as conversion_ts,
    cast("timestamp" as date)                                   as conversion_date,
    cast(received_at as timestamp)                              as received_ts,
    user_id,
    conversion_type,
    revenue_usd,
    date_diff('minute', "timestamp", received_at) / 60.0        as arrival_lag_hours,
    received_at > "timestamp" + interval 24 hour                as is_late_arrival
from {{ source('lake', 'conversions') }}
where conversion_id is not null
qualify row_number() over (partition by conversion_id order by received_at) = 1
