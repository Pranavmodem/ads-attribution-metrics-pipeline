# Open-Source Landscape: Ads Attribution & Marketing Analytics

Research on open-source projects relevant to this pipeline — what exists, what's
more advanced, and how to level up this project.

---

## Current Project Assessment

This pipeline implements **4 heuristic attribution models** (last-touch,
first-touch, linear, time-decay) plus standard ad metrics (CPM, CTR, ROAS, CPA).
While the architecture is clean, it's missing the **data-driven attribution**,
**Bayesian modeling**, and **causal inference** layers that distinguish
production-grade systems.

---

## Tier 1: Industry-Leading MMM Frameworks (Big Tech)

### Meta Robyn
- **GitHub:** https://github.com/facebookexperimental/Robyn
- **What:** AI/ML-powered Marketing Mix Modeling from Meta Marketing Science
- **Key features:** Ridge regression, multi-objective evolutionary optimization,
  time-series decomposition, adstock/saturation curves, budget allocation
- **Stack:** R (primary), Python wrapper | **License:** MIT
- **Why it matters:** Gold standard for open-source MMM. Models diminishing
  returns and carry-over effects that heuristic attribution completely misses.

### Google Meridian
- **GitHub:** https://github.com/google/meridian
- **What:** Google's next-gen Bayesian MMM framework (successor to LightweightMMM)
- **Key features:** Bayesian causal inference, geo-level data, MCMC via NUTS,
  GPU acceleration, incrementality experiment calibration, reach & frequency
- **Stack:** Python, JAX, TensorFlow Probability, NumPyro | **License:** Apache 2.0
- **Why it matters:** Most advanced open-source MMM. Bridges MMM with
  incrementality testing via experiment-as-priors.

### Google LightweightMMM (Archived)
- **GitHub:** https://github.com/google/lightweight_mmm
- **What:** Google's previous-gen lightweight Bayesian MMM (archived Jan 2026)
- **Stack:** Python, NumPyro, JAX | **License:** Apache 2.0
- **Why it matters:** Simpler entry point for learning Bayesian MMM concepts
  before moving to Meridian.

### PyMC-Marketing
- **GitHub:** https://github.com/pymc-labs/pymc-marketing
- **What:** Bayesian marketing toolbox — MMM + CLV + Buy-Till-You-Die models
- **Key features:** Adstock transforms, saturation curves, budget optimization,
  full uncertainty quantification, works with months of data (not years)
- **Stack:** Python, PyMC, PyTensor, ArviZ | **License:** Apache 2.0
- **Why it matters:** Most Pythonic MMM framework. Integrates MMM with CLV for
  holistic marketing analytics. Strongest statistical modeling capabilities.

---

## Tier 2: Multi-Touch Attribution Libraries

These implement **data-driven** attribution (Markov chains, Shapley values)
which is a major gap in this project's heuristic-only approach.

### ChannelAttribution
- **GitHub:** https://github.com/DavideAltomare/ChannelAttribution
- **What:** Markov Model for online multi-channel attribution
- **Key features:** k-order Markov chains, removal effect calculation,
  transition probability estimation, heuristic models
- **Stack:** C++ core, Python/R wrappers | **PyPI:** `ChannelAttribution`
- **Why it matters:** Academic/research standard for Markov attribution.
  C++ core makes it performant at scale.

### MTA (eeghor/mta)
- **GitHub:** https://github.com/eeghor/mta
- **What:** Most feature-complete open-source MTA library
- **Key features:** Shapley Value, Markov Chain, Logistic Regression,
  Additive Hazard, Position-Based, Time Decay models
- **Stack:** Python (pandas, numpy, scikit-learn) | **PyPI:** `mta`
- **Why it matters:** Implements both heuristic AND algorithmic (data-driven)
  models. Shapley values give mathematically fair credit allocation.

### DP6 Marketing-Attribution-Models
- **GitHub:** https://github.com/DP6/Marketing-Attribution-Models
- **What:** Python library with Markov chains + Shapley values + heuristics
- **PyPI:** `marketing-attribution-models`
- **Why it matters:** Clean API, easy to integrate, covers the full spectrum
  from simple heuristics to probabilistic models.

### Shapley Value MTA
- **GitHub:** https://github.com/bernard-mlab/Multi-Touch-Attribution_ShapleyValue
- **What:** Focused Python implementation of Shapley value for MTA
- **Why it matters:** Reference implementation for game-theory-based attribution.

---

## Tier 3: Causal Inference & Incrementality Testing

Essential for **validating** that attribution models measure real causal impact.

### Uber CausalML
- **GitHub:** https://github.com/uber/causalml
- **What:** Uplift modeling and causal inference with ML
- **Key features:** Meta-learners (S/T/X/R), uplift trees/forests, CEVAE,
  DragonNet, policy optimization, sensitivity analysis
- **Stack:** Python, scikit-learn, XGBoost, LightGBM, PyTorch | **License:** Apache 2.0
- **Stars:** ~4,100+
- **Why it matters:** Measures incremental ad campaign impact. Identifies which
  segments respond best to specific treatments.

### DoWhy (PyWhy)
- **GitHub:** https://github.com/py-why/dowhy
- **What:** End-to-end causal inference library
- **Key features:** Causal graphs, effect estimation, refutation/falsification
  API, counterfactual reasoning, root cause analysis
- **Stack:** Python | **License:** MIT | **Stars:** ~7,300
- **Why it matters:** Validates that attribution models measure true causal
  effects rather than correlations.

### EconML (Microsoft Research)
- **GitHub:** https://github.com/py-why/EconML
- **What:** Heterogeneous treatment effects from observational data
- **Key features:** Double ML, Orthogonal Random Forests, instrumental variables,
  dynamic treatment effects, confidence intervals, policy learning
- **Stack:** Python | **License:** MIT
- **Why it matters:** Understands how ad effectiveness varies across customer
  segments — critical for optimizing spend allocation.

---

## Tier 4: Event Collection & Data Infrastructure

### Snowplow
- **GitHub:** https://github.com/snowplow/snowplow
- **What:** Premier open-source event data pipeline for behavioral data
- **Key features:** Multi-platform trackers, real-time processing, JSONSchema
  validation, enrichments, warehouse loading
- **Stack:** Scala, JavaScript | **Stars:** ~7,000
- **Why it matters:** Provides the raw event data layer feeding attribution models.

### RudderStack
- **GitHub:** https://github.com/rudderlabs/rudder-server
- **What:** Open-source CDP (Segment alternative), warehouse-first
- **Key features:** 200+ integrations, event streaming, identity resolution
- **Stack:** Go | **Stars:** ~4,400

### OpenAttribution
- **GitHub:** https://github.com/OpenAttribution/open-attribution
- **What:** Open-source Mobile Measurement Partner (MMP)
- **Why it matters:** Only open-source project targeting mobile ad attribution
  (the domain of AppsFlyer, Adjust, Branch).

### Jitsu
- **GitHub:** https://github.com/jitsucom/jitsu
- **What:** Open-source Segment alternative, real-time data ingestion
- **Stack:** TypeScript, Go | **Stars:** ~4,600

---

## Tier 5: Analytics & Visualization Platforms

### PostHog
- **GitHub:** https://github.com/PostHog/posthog
- **What:** All-in-one: product analytics, web analytics, session replay,
  A/B testing, feature flags, data warehouse
- **Stack:** Python, TypeScript, ClickHouse, Kafka | **Stars:** ~32,000+
- **Why it matters:** Shows what a production-grade analytics platform looks like.

### Matomo
- **GitHub:** https://github.com/matomo-org/matomo
- **What:** Full Google Analytics alternative with multi-channel attribution
- **Stack:** PHP, MySQL | **Stars:** ~21,000+

### Plausible Analytics
- **GitHub:** https://github.com/plausible/analytics
- **What:** Privacy-first, cookie-free web analytics (<1KB script)
- **Stack:** Elixir, ClickHouse | **Stars:** ~24,000+

---

## Tier 6: Pipeline Orchestration

### Apache Airflow (already used)
- **GitHub:** https://github.com/apache/airflow | **Stars:** ~45,000

### Dagster (modern alternative)
- **GitHub:** https://github.com/dagster-io/dagster | **Stars:** ~15,200
- **Why consider:** Asset-based model (vs task-based), first-class dbt integration

### Prefect
- **GitHub:** https://github.com/PrefectHQ/prefect | **Stars:** ~18,200
- **Why consider:** Most Pythonic orchestrator, built-in retries and caching

---

## Curated Resource Lists

- [awesome-marketing-machine-learning](https://github.com/station-10/awesome-marketing-machine-learning) — ML libs for MMM, MTA, causal inference
- [awesome-adtech](https://github.com/AirGrid/awesome-adtech) — Ad tech software, datasets, tools
- [Awesome-Marketing-Science](https://github.com/shakostats/Awesome-Marketing-Science) — Geo incrementality, MMM, MTA, causal inference

---

## Gap Analysis: This Project vs. The Ecosystem

| Gap | Impact | What to Add | Reference Project |
|-----|--------|-------------|-------------------|
| No data-driven attribution | HIGH | Markov chains, Shapley values | ChannelAttribution, MTA |
| No MMM layer | HIGH | Media mix modeling w/ adstock & saturation | Meridian, Robyn, PyMC-Marketing |
| No Bayesian modeling | MEDIUM | Probabilistic inference with uncertainty | PyMC-Marketing |
| No causal inference | MEDIUM | Incrementality testing | CausalML, DoWhy |
| No CLV modeling | MEDIUM | Customer lifetime value prediction | PyMC-Marketing |
| No dashboards | HIGH | Interactive visualization | Streamlit |
| No Docker setup | MEDIUM | Containerized deployment | — |
| Empty transform layer | HIGH | `src/transform/` has no code | — |
| No dbt config | HIGH | Missing `dbt_project.yml` | dbt quickstart |
| Batch-only pipeline | LOW | Streaming support | Snowplow, Kafka |

---

## Recommended Integration Path

**Phase 1 — Biggest bang for the buck:**
1. Add Markov chain + Shapley value attribution (use `mta` or `ChannelAttribution`)
2. Build the Streamlit dashboard
3. Complete the dbt configuration (`dbt_project.yml`, `profiles.yml`)
4. Add Dockerfile

**Phase 2 — Advanced modeling:**
5. Add Bayesian MMM component (PyMC-Marketing)
6. Add incrementality testing (CausalML or DoWhy)
7. Add CLV modeling (PyMC-Marketing)

**Phase 3 — Production hardening:**
8. Streaming ingestion (Snowplow or Kafka)
9. Monitoring & alerting (Grafana, PagerDuty)
10. Privacy compliance (GDPR/CCPA aggregation)
