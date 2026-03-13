# Architecture: Ads Attribution Metrics Pipeline

## Overview

This pipeline ingests ad impression and conversion events, runs attribution logic to assign credit across touchpoints, and produces business metrics that stakeholders consume via self-service dashboards.

## Data Flow

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Ad Impression   │────▶│  GCS Raw     │────▶│  BigQuery Raw   │
│  Events (JSON)   │     │  Zone        │     │  (partitioned)  │
└─────────────────┘     └──────────────┘     └────────┬────────┘
                                                       │
┌─────────────────┐     ┌──────────────┐               │
│  Conversion      │────▶│  GCS Raw     │────▶──────────┤
│  Events (JSON)   │     │  Zone        │               │
└─────────────────┘     └──────────────┘               │
                                                       ▼
                                              ┌─────────────────┐
                                              │  dbt Staging     │
┌─────────────────┐                           │  (clean, dedup)  │
│  Campaign        │──────────────────────────▶└────────┬────────┘
│  Metadata        │                                    │
└─────────────────┘                                    ▼
                                              ┌─────────────────┐
                                              │  dbt Intermediate│
                                              │  (join, enrich)  │
                                              └────────┬────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │  dbt Marts       │
                                              │  (business       │
                                              │   metrics)       │
                                              └────────┬────────┘
                                                       │
                                          ┌────────────┴────────────┐
                                          ▼                         ▼
                                 ┌─────────────────┐    ┌──────────────────┐
                                 │  Tableau         │    │  Streamlit       │
                                 │  Dashboard       │    │  Internal Tool   │
                                 └─────────────────┘    └──────────────────┘
```

## Attribution Models

The pipeline supports four attribution models, configurable per run:

| Model | Logic | Best For |
|-------|-------|----------|
| Last Touch | 100% credit to final touchpoint | Direct response campaigns |
| First Touch | 100% credit to first touchpoint | Brand awareness campaigns |
| Linear | Equal credit across all touchpoints | Balanced multi-channel analysis |
| Time Decay | Exponential decay weighting recent touchpoints | Performance marketing |

## Data Quality Strategy

Quality checks run at three levels:

1. **Ingestion time** — schema validation, null checks, deduplication
2. **dbt tests** — uniqueness, not-null, accepted values, referential integrity
3. **Post-transform** — metric range checks, freshness monitoring, anomaly detection

## Key Design Decisions

### Why BigQuery over Snowflake
BigQuery is serverless and natively integrated with Cloud Composer (Airflow).
No cluster management overhead. For ad event data that's bursty (campaign launches),
serverless scaling is a better fit than pre-provisioned warehouses.

### Why Medallion Architecture
Raw → Staging → Intermediate → Marts creates clean separation of concerns.
When ad schemas change (new ad formats, new attribution signals), only the
staging layer needs updating. Business metric logic stays untouched.

### Why dbt for Transformations
The attribution metrics layer is fundamentally SQL logic. dbt makes it version-controlled,
testable, and documented. PySpark is used in the ingestion layer where we need
programmatic data quality logic, but the business metrics are pure SQL.
