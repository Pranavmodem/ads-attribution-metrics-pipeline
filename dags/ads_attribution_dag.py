"""
ads_attribution_dag.py
Daily run of the attribution pipeline for one day's partition (Airflow 3).

    ingest_impressions --+
    ingest_clicks -------+--> quality_gate --> dbt_build --> export_dashboard
    ingest_conversions --+
    ingest_campaigns ----+

Every task runs the same command `make pipeline` runs, so Airflow and a laptop
execute identical code. The four loads write separate partition files and can
run in parallel; dbt is the only writer to the DuckDB warehouse, so the DAG
allows one active run at a time.

The run at 06:00 UTC loads the previous day. Point AIRFLOW__CORE__DAGS_FOLDER
at this directory; set PIPELINE_HOME if the repo is not this folder's parent.
"""
import os
from datetime import datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

PIPELINE_HOME = os.environ.get("PIPELINE_HOME", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PYTHON = os.environ.get("PIPELINE_PYTHON", os.path.join(PIPELINE_HOME, ".venv", "bin", "python"))
DBT = os.environ.get("PIPELINE_DBT", os.path.join(PIPELINE_HOME, ".venv", "bin", "dbt"))
PARTITION = "{{ macros.ds_add(ds, -1) }}"  # yesterday, relative to the run date


def task(task_id: str, command: str) -> BashOperator:
    return BashOperator(
        task_id=task_id,
        bash_command=command,
        cwd=PIPELINE_HOME,
        env={"PYTHONPATH": PIPELINE_HOME},
        append_env=True,
    )


with DAG(
    dag_id="ads_attribution_pipeline",
    description="Ingest a day of ad events, gate on quality, build seven attribution models in dbt, export",
    schedule="0 6 * * *",
    start_date=datetime(2026, 8, 1),
    catchup=False,
    max_active_runs=1,
    default_args={"owner": "data-engineering", "retries": 2, "retry_delay": timedelta(minutes=5),
                  "execution_timeout": timedelta(hours=1)},
    tags=["ads", "attribution", "dbt", "duckdb"],
) as dag:
    ingest = [
        task(f"ingest_{entity}", f"{PYTHON} -m src.ingestion --entity {entity} --date {PARTITION}")
        for entity in ("impressions", "clicks", "conversions", "campaigns")
    ]
    quality_gate = task("quality_gate", f"{PYTHON} -m src.utils.quality_checks --date {PARTITION}")
    dbt_build = task("dbt_build", f"{DBT} build --project-dir . --profiles-dir .")
    export_dashboard = task("export_dashboard", f"{PYTHON} -m src.export")

    ingest >> quality_gate >> dbt_build >> export_dashboard
