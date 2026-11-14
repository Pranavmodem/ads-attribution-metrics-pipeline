-- One row per user reached: their channel path inside the lookback window and
-- whether they converted. Same windowing as src.metrics.advanced_attribution.build_journeys:
-- converting users look back from their first conversion, everyone else from
-- their last impression. Consecutive repeats of a channel collapse into one step.

with first_conversion as (
    select user_id, min(conversion_ts) as conversion_ts
    from {{ ref('stg_conversions') }}
    group by user_id
),

anchored as (
    select
        i.user_id,
        i.impression_ts,
        i.channel,
        c.conversion_ts,
        coalesce(c.conversion_ts, max(i.impression_ts) over (partition by i.user_id)) as anchor_ts
    from {{ ref('stg_impressions') }} i
    left join first_conversion c using (user_id)
),

windowed as (
    select
        *,
        lag(channel) over (partition by user_id order by impression_ts) as previous_channel
    from anchored
    where impression_ts <= anchor_ts
      and impression_ts >= anchor_ts - to_days({{ var('attribution_window_days') }})
)

select
    user_id,
    string_agg(channel, ' > ' order by impression_ts)
        filter (where previous_channel is distinct from channel)               as path,
    count(*)                                                                    as touches,
    count(distinct channel)                                                     as distinct_channels,
    min(impression_ts)                                                          as first_touch_ts,
    max(impression_ts)                                                          as last_touch_ts,
    any_value(conversion_ts)                                                    as conversion_ts,
    any_value(conversion_ts) is not null                                        as converted,
    date_diff('minute', min(impression_ts), any_value(conversion_ts)) / 1440.0  as days_to_convert
from windowed
group by user_id
