"""
export.py
Writes the dashboard's data file from the warehouse marts.

    python -m src.export                     # -> docs/data/dashboard.json

The dashboard reads nothing else, so everything it shows comes out of dbt
models that passed their tests. Also folds in the dbt run results and the
quality gate report so the dashboard can show the pipeline's own health.
"""
import argparse
import json
import logging
import math
import os
import re
from datetime import date, datetime, timezone

import duckdb

from src.utils.config import PipelineConfig
from src.utils.logging_config import setup_logging

logger = logging.getLogger(__name__)


def _clean(value):
    """JSON-safe scalars: dates to ISO strings, NaN/inf to null, floats rounded."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else round(value, 6)
    if hasattr(value, "item"):  # numpy / decimal scalars
        return _clean(value.item())
    return value


def _rows(con, sql: str) -> list:
    rel = con.sql(sql)
    cols = rel.columns
    return [{c: _clean(v) for c, v in zip(cols, row)} for row in rel.fetchall()]


def _dbt_summary(target_dir: str) -> dict:
    """Pass/fail for every test and model in the last dbt build, with readable names."""
    try:
        with open(os.path.join(target_dir, "run_results.json")) as f:
            run = json.load(f)
        with open(os.path.join(target_dir, "manifest.json")) as f:
            nodes = json.load(f)["nodes"]
    except FileNotFoundError:
        logger.warning("No dbt run results found; run `make transform` first")
        return {}

    tests, models = [], []
    for result in run["results"]:
        node = nodes.get(result["unique_id"], {})
        kind = node.get("resource_type")
        if kind == "model":
            models.append({"name": node["name"], "status": result["status"],
                           "language": node.get("language", "sql"),
                           "schema": node.get("schema"), "seconds": round(result["execution_time"], 2)})
        elif kind == "test":
            meta = node.get("test_metadata")
            if meta:  # generic test: unique, not_null, relationships, ...
                target = (node.get("attached_node") or "").split(".")[-1]
                column = node.get("column_name") or meta["kwargs"].get("column_name")
                name = f"{meta['name']} · {target}{'.' + column if column else ''}"
                description = None
            else:     # singular test: first comment line of the SQL explains it
                name = node["name"]
                match = re.search(r"^\s*--\s*(.+)$", node.get("raw_code", ""), re.M)
                description = match.group(1).strip() if match else None
            tests.append({"name": name, "status": result["status"], "kind": "generic" if meta else "singular",
                          "description": description, "failures": result.get("failures")})

    return {
        "finished_at": run["metadata"]["generated_at"],
        "elapsed_seconds": round(run["elapsed_time"], 1),
        "dbt_version": run["metadata"]["dbt_version"],
        "models": models,
        "tests": sorted(tests, key=lambda t: (t["kind"] != "singular", t["name"])),
    }


def build(warehouse_path: str, target_dir: str = "target", quality_report: str = "data/quality/report.json") -> dict:
    con = duckdb.connect(warehouse_path, read_only=True)
    window = PipelineConfig.from_env().attribution_window_days

    totals = _rows(con, """
        select
            (select count(*) from staging.stg_impressions)                  as impressions,
            (select count(distinct user_id) from staging.stg_impressions)   as users_reached,
            (select count(*) from staging.stg_clicks)                       as clicks,
            (select sum(cost_usd) from staging.stg_impressions)             as spend_usd,
            (select count(*) from staging.stg_conversions)                  as conversions,
            (select sum(revenue_usd) from staging.stg_conversions)          as revenue_usd,
            (select count(*) from staging.stg_conversions where is_late_arrival) as late_conversions,
            (select count(*) from staging.stg_campaigns)                    as campaigns,
            (select count(*) from intermediate.int_user_journeys where converted) as converting_users,
            (select min(impression_date) from staging.stg_impressions)      as start_date,
            (select max(impression_date) from staging.stg_impressions)      as end_date
    """)[0]
    totals["ctr"] = totals["clicks"] / totals["impressions"]
    totals["roas"] = totals["revenue_usd"] / totals["spend_usd"]
    totals["cpa_usd"] = totals["spend_usd"] / totals["conversions"]
    totals["cpm_usd"] = totals["spend_usd"] / totals["impressions"] * 1000
    totals["conversion_rate"] = totals["converting_users"] / totals["users_reached"]

    has_truth = bool(_rows(con, """
        select count(*) as n from information_schema.tables
        where table_schema = 'marts' and table_name = 'mart_model_accuracy'
    """)[0]["n"])

    quality = None
    if os.path.exists(quality_report):
        with open(quality_report) as f:
            quality = json.load(f)

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "attribution_window_days": window,
            "synthetic": has_truth,
        },
        "totals": totals,
        "daily": _rows(con, """
            select date, impressions, users_reached, clicks, spend_usd, conversions, revenue_usd
            from marts.mart_daily_performance order by date
        """),
        "accuracy": _rows(con, """
            select model, model_label, model_family, mean_abs_error_pp, max_abs_error_pp,
                   worst_channel, accuracy_rank
            from marts.mart_model_accuracy order by accuracy_rank
        """) if has_truth else [],
        "channels": _rows(con, """
            select model, model_label, model_family, channel, credit, attributed_conversions,
                   attributed_revenue_usd, spend_usd, impressions, roas, cpa_usd, true_credit, error_pp
            from marts.mart_channel_attribution order by model, channel
        """),
        "campaigns": _rows(con, """
            select model, campaign_id, campaign_name, advertiser_name, channel, status, impressions,
                   users_reached, clicks, spend_usd, conversions, revenue_usd, ctr, cpm_usd,
                   conversion_rate, roas, cpa_usd
            from marts.mart_campaign_performance order by model, spend_usd desc
        """),
        "paths": _rows(con, """
            select path, steps, users, conversions, conversion_rate, avg_touches, median_days_to_convert
            from marts.mart_journey_paths order by conversions desc, users desc limit 12
        """),
        "path_lengths": _rows(con, "select * from marts.mart_journey_lengths order by touches"),
        "pipeline": {
            "ingestion": _rows(con, "select * from marts.mart_ingestion_audit order by entity"),
            "quality": quality,
            "dbt": _dbt_summary(target_dir),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="docs/data/dashboard.json")
    args = parser.parse_args()
    setup_logging()

    data = build(PipelineConfig.from_env().warehouse_path)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    logger.info(f"Wrote {args.out} ({os.path.getsize(args.out) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
