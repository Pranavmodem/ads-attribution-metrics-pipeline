# Ads Attribution Metrics Pipeline

> An end-to-end analytics engineering pipeline that ingests ad impression and conversion event data, builds attribution models, and exposes self-service metrics dashboards for business stakeholders.

## Why I Built This

Working in ad tech, I kept running into the same problem: business teams needed to understand which ads actually drove real-world outcomes (store visits, purchases), but the data was fragmented across impression logs, conversion events, and third-party attribution signals. Every analysis was a one-off SQL query, and nobody trusted the numbers because there was no single source of truth.

This project is my take on building that foundation — a clean, tested, observable pipeline that transforms raw ad event data into reliable attribution metrics that business teams can self-serve without filing a data request.

## Architecture

```
[Ad Impression Events]  →  [Cloud Composer / Airflow]  →  [GCS Raw Zone]
[Conversion Events]     →        (orchestration)        →  (Parquet)
[Campaign Metadata]     →                               →
        ↓
[BigQuery Staging Layer]  →  [dbt Transformations]  →  [BigQuery Marts]
   (type-cast, clean)        (attribution logic)        (business metrics)
        ↓
[Tableau / Streamlit Dashboard]  ←  Self-Service Metrics Layer
```

## Tech Stack

| Layer | Tool | Why This Tool |
|-------|------|---------------|
| Orchestration | Apache Airflow (Cloud Composer) | Production-grade scheduling with deep GCP integration; I've used it extensively for similar pipelines |
| Ingestion | Python + GCS | Lightweight, flexible for multiple source formats (JSON, CSV, Parquet) |
| Storage | BigQuery | Serverless, columnar, handles TB-scale ad event data cost-effectively |
| Transformation | dbt | SQL-first, version controlled, testable — perfect for metrics logic that business teams need to trust |
| Data Quality | dbt tests + custom Python checks | Schema enforcement, freshness checks, and reconciliation logic baked into the pipeline |
| Visualization | Tableau / Streamlit | Tableau for enterprise self-service; Streamlit for rapid prototyping and internal tools |
| Monitoring | Structured logging + Grafana | End-to-end observability into DAG execution and data freshness |

## What's Inside

```
src/ingestion/          - Loads raw ad event data (impressions, conversions, campaigns) into GCS
src/transform/          - PySpark transformations for heavy-lift processing
src/metrics/            - Core attribution and measurement metric calculations
src/utils/              - Logging, config management, data quality helpers
dags/                   - Airflow DAGs: daily attribution pipeline + data quality checks
models/staging/         - dbt staging models: clean, type-cast, deduplicate raw events
models/intermediate/    - dbt intermediate: join impressions ↔ conversions, sessionization
models/marts/           - dbt marts: final business metrics (CPM, CTR, ROAS, attribution)
tests/                  - Unit tests for transformation and metric logic
dashboards/             - Tableau workbook config + Streamlit dashboard code
notebooks/              - Exploratory analysis and metric validation
```

## Getting Started

```bash
# 1. Clone and install
git clone https://github.com/pranavmodem/ads-attribution-metrics-pipeline
cd ads-attribution-metrics-pipeline
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Fill in your GCP project ID, BigQuery dataset, GCS bucket

# 3. Generate sample data
make generate-data

# 4. Run the pipeline
make pipeline     # Runs ingestion → transform → metrics
make test         # Run unit tests
make quality      # Run data quality checks
```

## Core Metrics

The pipeline produces these business metrics in the marts layer:

| Metric | Definition | Business Use |
|--------|-----------|--------------|
| **CPM** | Cost per 1,000 impressions | Campaign cost efficiency |
| **CTR** | Click-through rate (clicks / impressions) | Creative effectiveness |
| **Conversion Rate** | Conversions / clicks | Funnel health |
| **ROAS** | Revenue attributed / ad spend | Return on ad investment |
| **View-Through Attribution** | Conversions within N-day window post-impression | Measures brand lift beyond clicks |
| **Multi-Touch Attribution** | Weighted credit across touchpoints | Fair attribution across campaign mix |
| **Fill Rate** | Filled impressions / available inventory | Supply utilization |
| **Frequency** | Average impressions per unique user | Exposure management |

## Key Design Decisions

**Why dbt over raw SQL scripts for the transformation layer**

I considered keeping transformations as raw SQL files orchestrated by Airflow, which is simpler. But dbt gives me version-controlled models, built-in testing (not null, unique, accepted_values), documentation generation, and lineage graphs. For a metrics layer that business teams need to trust, the testing alone makes dbt worth it. The tradeoff is added complexity in the dev setup, but it pays for itself the first time someone asks "why did this metric change?"

**Why a medallion architecture (staging → intermediate → marts) over flat tables**

It's tempting to go straight from raw data to final metrics in one big query. But ad data is messy — late-arriving conversions, duplicate impressions, schema changes from new ad products. The staging layer handles all of that cleaning in isolation, so the business logic in the marts layer stays clean and readable. When a new ad format launches and the schema changes, I only need to update one staging model instead of every downstream query.

**Why Airflow over Prefect/Dagster for orchestration**

Airflow via Cloud Composer is the most battle-tested option for GCP-native pipelines. I've run production Airflow DAGs at scale and know the failure modes. Prefect and Dagster have nicer developer experiences, but for a production ads pipeline where reliability matters more than DX, I'd rather use the tool I can debug at 2am.

## What I'd Do With More Time

- [ ] Add Great Expectations for more granular data quality assertions
- [ ] Implement incremental loading with merge strategies for late-arriving conversions
- [ ] Add a real-time path using Kafka + Flink for streaming attribution (currently batch-only)
- [ ] Build an alerting layer when pipeline SLA is breached or metric anomalies detected
- [ ] Add privacy-safe aggregation for GDPR/CCPA compliance in attribution
- [ ] Containerize the full pipeline with Docker Compose for local development

## Data Source

This project uses synthetically generated ad event data that mirrors real-world ad tech patterns: impression logs with placement/creative metadata, conversion events with attribution windows, and campaign configuration data. The synthetic generator (`src/utils/data_generator.py`) creates realistic distributions including time-decay patterns, multi-touch sequences, and late-arriving events.

No real user data is used. The schema is designed to be compatible with common ad server export formats.
