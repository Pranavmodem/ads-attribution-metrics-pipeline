# Architecture: Ads Attribution Metrics Pipeline

## Overview

This pipeline ingests ad impression, click, and conversion events across 7 marketing channels, runs 7 attribution models (4 heuristic + 3 data-driven), and produces business metrics consumed via an interactive Streamlit dashboard.

## Data Flow

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Ad Impression   │────▶│  GCS Raw     │────▶│  BigQuery Raw   │
│  Events          │     │  Zone        │     │  (partitioned)  │
└─────────────────┘     └──────────────┘     └────────┬────────┘
                                                       │
┌─────────────────┐     ┌──────────────┐               │
│  Click Events    │────▶│  GCS Raw     │────▶──────────┤
│                  │     │  Zone        │               │
└─────────────────┘     └──────────────┘               │
                                                       │
┌─────────────────┐     ┌──────────────┐               │
│  Conversion      │────▶│  GCS Raw     │────▶──────────┤
│  Events          │     │  Zone        │               │
└─────────────────┘     └──────────────┘               │
                                                       ▼
                                              ┌─────────────────┐
┌─────────────────┐                           │  dbt Staging     │
│  Campaign        │──────────────────────────▶│  (clean, dedup)  │
│  Metadata        │                           └────────┬────────┘
└─────────────────┘                                     │
                                                        ▼
                                              ┌─────────────────┐
                                              │  dbt Intermediate│
                                              │  (join, enrich)  │
                                              └────────┬────────┘
                                                       │
                             ┌──────────────────────────┤
                             ▼                          ▼
                   ┌───────────────────┐     ┌─────────────────┐
                   │  Attribution       │     │  dbt Marts       │
                   │  Engine (Python)   │     │  (business       │
                   │                    │     │   metrics)       │
                   │  Heuristic:        │     └────────┬────────┘
                   │  - Last Touch      │              │
                   │  - First Touch     │              │
                   │  - Linear          │              ▼
                   │  - Time Decay      │    ┌──────────────────┐
                   │                    │    │  Streamlit        │
                   │  Data-Driven:      │───▶│  Dashboard        │
                   │  - Markov Chain    │    │  (5 pages)        │
                   │  - Shapley Value   │    │                   │
                   │  - Position Based  │    │  - Overview       │
                   └───────────────────┘    │  - Attribution    │
                                            │  - Campaigns      │
                                            │  - Channels       │
                                            │  - Data Quality   │
                                            └──────────────────┘
```

## Attribution Models

The pipeline supports **7 attribution models** across two categories:

### Heuristic Models (rule-based)

| Model | Logic | Best For |
|-------|-------|----------|
| Last Touch | 100% credit to final touchpoint | Direct response campaigns |
| First Touch | 100% credit to first touchpoint | Brand awareness campaigns |
| Linear | Equal credit across all touchpoints | Balanced multi-channel analysis |
| Time Decay | Exponential decay weighting recent touchpoints | Performance marketing |

### Data-Driven Models (learned from journey data)

| Model | Logic | Best For |
|-------|-------|----------|
| Markov Chain | Transition probability matrix + removal effect | Understanding sequential channel dependencies |
| Shapley Value | Game-theoretic fair credit via coalition analysis | Mathematically fairest attribution (satisfies efficiency, symmetry, null-player axioms) |
| Position Based | 40/20/40 (first/middle/last) weighting | Balanced awareness + conversion credit |

### How the Markov Chain Model Works

1. Build user journeys: sequences of channels before conversion (e.g., `Display → Social → Search → Conversion`)
2. Construct a transition probability matrix between states: `(start)`, channels, `(conversion)`, `(null)`
3. For each channel, compute the **removal effect**: how much does the overall conversion rate drop if we remove that channel from the graph?
4. Normalize removal effects to get attribution weights

### How the Shapley Value Model Works

1. For every possible subset (coalition) of channels, compute the conversion rate
2. For each channel, compute its marginal contribution across all coalitions it could join
3. Weight by the Shapley formula: `|S|! * (n-|S|-1)! / n!`
4. Normalize to get attribution weights

Note: Shapley is O(2^n) on channels, so a guard limits computation to 12 channels max.

## Marketing Channels

The pipeline models 7 channels with distinct performance profiles:

| Channel | CTR | Conv Rate | Avg CPC | Role |
|---------|-----|-----------|---------|------|
| Paid Search | 3.5% | 4.0% | $2.50 | High intent capture |
| Social | 1.2% | 1.5% | $1.20 | Awareness + retargeting |
| Display | 0.4% | 0.8% | $0.80 | Upper funnel reach |
| Video | 1.8% | 1.2% | $3.50 | Brand building |
| Email | 2.5% | 5.0% | $0.30 | Highest CVR, retention |
| Native | 0.8% | 1.0% | $1.50 | Content-driven |
| Affiliate | 1.5% | 2.5% | $1.80 | Performance partnerships |

## Data Quality Strategy

Quality checks run at three levels:

1. **Ingestion time** — schema validation, null checks, deduplication, type casting
2. **dbt tests** — uniqueness, not-null, accepted values, referential integrity
3. **Dashboard monitoring** — column completeness visualization, daily volume anomaly detection (z-score), distribution analysis, freshness tracking

## Key Design Decisions

### Why Both Heuristic and Data-Driven Attribution

Heuristic models are simple and every stakeholder understands them. But last-touch systematically overvalues bottom-funnel channels. The dashboard shows both model types side-by-side with a divergence analysis, so teams can see exactly where the models disagree and make informed budget decisions.

### Why BigQuery over Snowflake

BigQuery is serverless and natively integrated with Cloud Composer (Airflow). No cluster management overhead. For ad event data that's bursty (campaign launches), serverless scaling is a better fit than pre-provisioned warehouses.

### Why Medallion Architecture

Raw → Staging → Intermediate → Marts creates clean separation of concerns. When ad schemas change (new ad formats, new attribution signals), only the staging layer needs updating. Business metric logic stays untouched.

### Why dbt for Transformations

The attribution metrics layer is fundamentally SQL logic. dbt makes it version-controlled, testable, and documented. The attribution engine uses Python (pandas) where probabilistic/algorithmic models require it, but business metrics are pure SQL.

### Why Streamlit over Tableau for the Dashboard

Streamlit allows tightly coupling the attribution engine (Python) with the visualization layer. The 7 attribution models run in Python and feed directly into Plotly charts — no need for an intermediate data export step. Streamlit also makes it trivial to add interactive controls (date filters, channel selectors, model comparisons).
