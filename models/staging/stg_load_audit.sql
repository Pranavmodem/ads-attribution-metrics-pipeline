-- What the loader wrote and what it set aside, per entity and partition.

select
    entity,
    cast(dt as date)                    as partition_date,
    rows_loaded,
    duplicates_dropped,
    null_keys_dropped,
    late_arrivals,
    cast(loaded_at as timestamptz)      as loaded_at
from {{ source('lake', 'load_audit') }}
