-- One row per click, deduplicated across partitions.

select
    click_id,
    impression_id,
    cast("timestamp" as timestamp)      as click_ts,
    cast("timestamp" as date)           as click_date,
    user_id,
    campaign_id,
    channel
from {{ source('lake', 'clicks') }}
where click_id is not null
qualify row_number() over (partition by click_id order by "timestamp") = 1
