"""
ads_attribution_dag.py
Daily Airflow DAG for the ads attribution metrics pipeline.

Schedule: Runs daily at 06:00 UTC (after ad servers flush overnight data).
Pipeline: ingest → validate → transform → dbt run → quality checks → notify
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.cncf.kubernetes.operators.kubernetes_pod import KubernetesPodOperator
from airflow.operators.bash import BashOperator
from airflow.utils.trigger_rule import TriggerRule


default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}


with DAG(
    dag_id="ads_attribution_metrics_pipeline",
    default_args=default_args,
    description="Daily ads attribution pipeline: ingest → transform → metrics → quality",
    schedule_interval="0 6 * * *",  # Daily at 06:00 UTC
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["ads", "attribution", "metrics", "production"],
) as dag:

    # ── Task 1: Ingest impression events ──
    ingest_impressions = KubernetesPodOperator(
        task_id="ingest_impressions",
        name="ingest-impressions",
        namespace="data-pipelines",
        image="ads-pipeline:latest",
        cmds=["python", "-m", "src.ingestion.impression_loader"],
        arguments=["{{ ds }}"],
        env_vars={
            "GCP_PROJECT_ID": "{{ var.value.gcp_project_id }}",
            "GCS_BUCKET": "{{ var.value.gcs_bucket }}",
        },
        resources={
            "request_memory": "2Gi",
            "request_cpu": "1",
            "limit_memory": "4Gi",
            "limit_cpu": "2",
        },
        is_delete_operator_pod=True,
        get_logs=True,
    )

    # ── Task 2: Ingest conversion events ──
    ingest_conversions = KubernetesPodOperator(
        task_id="ingest_conversions",
        name="ingest-conversions",
        namespace="data-pipelines",
        image="ads-pipeline:latest",
        cmds=["python", "-m", "src.ingestion.conversion_loader"],
        arguments=["{{ ds }}"],
        env_vars={
            "GCP_PROJECT_ID": "{{ var.value.gcp_project_id }}",
            "GCS_BUCKET": "{{ var.value.gcs_bucket }}",
            "ATTRIBUTION_WINDOW_DAYS": "30",
        },
        resources={
            "request_memory": "2Gi",
            "request_cpu": "1",
            "limit_memory": "4Gi",
            "limit_cpu": "2",
        },
        is_delete_operator_pod=True,
        get_logs=True,
    )

    # ── Task 3: Run data quality checks on raw data ──
    quality_checks_raw = BashOperator(
        task_id="quality_checks_raw",
        bash_command="python -m src.utils.quality_checks --entity impressions --date {{ ds }} && "
                     "python -m src.utils.quality_checks --entity conversions --date {{ ds }}",
    )

    # ── Task 4: Run dbt transformations (staging → intermediate → marts) ──
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command="cd models && dbt run --profiles-dir ../ --target prod --vars '{run_date: {{ ds }}}'",
    )

    # ── Task 5: Run dbt tests (schema + data quality) ──
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command="cd models && dbt test --profiles-dir ../ --target prod",
    )

    # ── Task 6: Notify on completion (success or failure) ──
    notify_success = PythonOperator(
        task_id="notify_success",
        python_callable=lambda **ctx: print(
            f"Pipeline succeeded for {ctx['ds']}: "
            f"attribution metrics updated in marts layer."
        ),
        trigger_rule=TriggerRule.ALL_SUCCESS,
    )

    notify_failure = PythonOperator(
        task_id="notify_failure",
        python_callable=lambda **ctx: print(
            f"Pipeline FAILED for {ctx['ds']}. Check logs."
        ),
        trigger_rule=TriggerRule.ONE_FAILED,
    )

    # ── DAG Dependencies ──
    # Impressions and conversions ingest in parallel
    [ingest_impressions, ingest_conversions] >> quality_checks_raw
    quality_checks_raw >> dbt_run >> dbt_test
    dbt_test >> [notify_success, notify_failure]
