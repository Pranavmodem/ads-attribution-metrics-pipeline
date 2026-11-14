-- Totals per entity from the loader's audit records.

select
    entity,
    count(*)                        as partitions,
    min(partition_date)             as first_partition,
    max(partition_date)             as last_partition,
    sum(rows_loaded)                as rows_loaded,
    sum(duplicates_dropped)         as duplicates_dropped,
    sum(null_keys_dropped)          as null_keys_dropped,
    sum(late_arrivals)              as late_arrivals,
    max(loaded_at)                  as last_loaded_at
from {{ ref('stg_load_audit') }}
group by entity
