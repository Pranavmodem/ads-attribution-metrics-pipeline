-- One row per impression, deduplicated across partitions.
-- bid_price_usd is the clearing price quoted as a CPM, so one impression costs CPM / 1000.

select
    impression_id,
    cast("timestamp" as timestamp)      as impression_ts,
    cast("timestamp" as date)           as impression_date,
    user_id,
    campaign_id,
    channel,
    placement_id,
    creative_id,
    user_segment_id,
    lower(device_type)                  as device_type,
    upper(geo_country)                  as geo_country,
    bid_price_usd                       as clearing_cpm_usd,
    bid_price_usd / 1000.0              as cost_usd
from {{ source('lake', 'impressions') }}
where impression_id is not null
qualify row_number() over (partition by impression_id order by "timestamp") = 1
