-- Latest snapshot of each campaign.

select
    campaign_id,
    campaign_name,
    advertiser_name,
    channel,
    status,
    budget_usd,
    dt                                  as snapshot_date
from {{ source('lake', 'campaigns') }}
qualify row_number() over (partition by campaign_id order by dt desc) = 1
