# Architecture

How data moves from simulated ad servers to the dashboard, and why each piece is
built the way it is. The [README](../README.md) covers results and how to run it.

## Data flow

```
make data          data/raw/{impressions,clicks,conversions,campaigns}.parquet
                     │   the "upstream exports", defects included
python -m          ▼
src.ingestion      data/lake/<entity>/dt=YYYY-MM-DD/part-0.parquet
                   data/lake/_audit/<entity>/dt=YYYY-MM-DD.json
                     │
python -m          ▼   exit 1 on any error-level failure
src.utils.quality_checks   data/quality/report.json
                     │
dbt build          ▼   data/warehouse.duckdb
                   staging        views: dedupe across partitions, derive cost
                   intermediate   int_user_journeys
                   attribution    Python models: touchpoints, channel credits, ground truth
                   marts          daily, campaign, channel, model accuracy, journeys, audit
                     │   44 tests run inside the same build
python -m          ▼
src.export         docs/data/dashboard.json  ->  docs/index.html (GitHub Pages)
```

Airflow (`dags/ads_attribution_dag.py`) runs those same commands for one day's
partition: the four entity loads in parallel, then the gate, `dbt build`, and the
export.

## Lake layout

| Entity | Partitioned by | Why |
| --- | --- | --- |
| impressions | event date | Delivery is reported by the day it happened |
| clicks | event date | Same |
| conversions | arrival date (`received_at`) | A conversion that arrives three days late lands in the partition of the day it arrived. Older partitions are never rewritten; staging deduplicates across them and keeps the first copy received |
| campaigns | load date, full snapshot | It is a dimension; staging keeps each campaign's latest snapshot |

Each load overwrites the partitions it touches, so rerunning a day gives the same
result. The loader keeps the rows it sets aside (null keys, duplicate keys) out of
the lake and counts them per partition in the audit record, which feeds the
`mart_ingestion_audit` table and the dashboard's pipeline section.

`LAKE_ROOT` is a path prefix. Point it at `gs://bucket/raw` with `gcsfs` installed
and the same code writes to Cloud Storage.

## Warehouse

| Schema | Model | Grain |
| --- | --- | --- |
| staging | `stg_impressions`, `stg_clicks`, `stg_conversions`, `stg_campaigns`, `stg_load_audit` | one row per event or entity |
| intermediate | `int_user_journeys` | one row per user reached: channel path in the window, converted or not |
| attribution | `attribution_touchpoints` (Python) | model × conversion × credited impression |
| attribution | `attribution_channel_credits` (Python) | model × channel, shares summing to 1 |
| attribution | `attribution_ground_truth` (Python) | channel; synthetic data only |
| marts | `mart_daily_performance` | day |
| marts | `mart_campaign_performance` | heuristic model × campaign |
| marts | `mart_channel_attribution` | model × channel, with ROAS and the gap to the truth |
| marts | `mart_model_accuracy` | model |
| marts | `mart_journey_paths`, `mart_journey_lengths` | path; impression count |
| marts | `mart_ingestion_audit` | entity |

The Python models import `src/metrics`, the same code the unit tests cover. Setting
the dbt var `synthetic_ground_truth: false` disables the ground-truth model and the
accuracy mart, which is what a run on real data would do.

## Tests

| Layer | What it checks |
| --- | --- |
| pytest (45) | Model math against hand-computed cases (Markov removal effects, Shapley efficiency and symmetry, position weights, window edges), generator properties, loader idempotency and partitioning, quality gate exit codes |
| Quality gate (24) | Each lake partition before dbt runs: schema, completeness, unique keys, value ranges, late-arrival share, freshness, volume against the trailing 14 days |
| dbt schema tests (38) | unique, not null, accepted values, relationships |
| dbt singular tests (6) | credits sum to one per conversion and per model; no credit outside the window; clicks follow their impressions; spend reconciles across marts; campaign conversions reconcile with attributed conversions |

## The ground truth

The generator draws each user's journey (more awareness channels early, more
intent channels late), then decides whether the user converts with

    logit P(convert) = -4.7 + Σ effect_c · (1 − 0.5^n_c) + 0.35 · [Display or Video] · [Paid Search]

where `n_c` is how many impressions of channel `c` the user saw. The true credit
of a channel is its exact Shapley share of `P(convert | exposures) − P(convert | none)`,
computed per user from those coefficients and summed over all users. The
attribution models never see the coefficients; they see only the event logs.

## Decisions

**DuckDB instead of a cloud warehouse.** The project has to run anywhere with one
command, including CI. DuckDB reads the Parquet lake directly and dbt-duckdb runs
Python models in-process. The cost is a single-writer warehouse, so the DAG allows
one active run.

**Attribution as dbt Python models.** The models are pandas and NumPy code, but
running them as dbt nodes puts them in the same lineage graph and the same build
as the SQL and the tests. A failing credit-sum test stops the marts from building.

**A static dashboard.** The page reads one JSON file the pipeline exports from the
marts, so it loads instantly from GitHub Pages and shows only numbers that passed
the dbt tests. It replaced a Streamlit app that recomputed everything from raw files
in the browser through Pyodide and took 15 to 30 seconds to start.

**Synthetic data with planted defects.** Duplicates, re-sent events, and late
arrivals give the dedup logic, partitioning, and quality gate something real to
catch.
