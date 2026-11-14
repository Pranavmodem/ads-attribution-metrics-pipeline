{{ config(enabled=var('synthetic_ground_truth')) }}
-- How far each model's channel shares are from the true shares, in percentage points.

select
    model,
    model_label,
    model_family,
    avg(abs(error_pp))                              as mean_abs_error_pp,
    max(abs(error_pp))                              as max_abs_error_pp,
    arg_max(channel, abs(error_pp))                 as worst_channel,
    rank() over (order by avg(abs(error_pp)))       as accuracy_rank
from {{ ref('mart_channel_attribution') }}
where model != 'ground_truth'
group by 1, 2, 3
