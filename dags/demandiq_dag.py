"""
Apache Airflow DAG: DemandIQ Enterprise ETL & Forecasting Workflow
Schedules, coordinates, and monitors daily batch ingestion and analytics.
Compatible with Apache Airflow 2.x & 3.x / Cloud Composer / Managed Airflow.
"""
from datetime import datetime, timedelta

try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
    from airflow.operators.bash import BashOperator
    from airflow.operators.empty import EmptyOperator
except ImportError:
    # Allows module to be imported and validated even if airflow package isn't locally installed
    DAG = None
    PythonOperator = None
    BashOperator = None
    EmptyOperator = None

default_args = {
    "owner": "data_engineering_team",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "email": ["alerts@demandiq.internal"],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

def task_extract_sources(**context):
    from pipelines.extract import extract_all
    datasets = extract_all()
    return f"Extracted {len(datasets)} datasets successfully."

def task_clean_validate(**context):
    from pipelines.extract import extract_all
    from pipelines.transform import transform_all
    raw_datasets = extract_all()
    clean_op, star_schema, dq = transform_all(raw_datasets)
    if not dq.validation_passed:
        raise ValueError(f"Data quality threshold failed. Acceptance: {dq.acceptance_rate_pct}%")
    return f"Validated {dq.final_valid_records} clean records."

def task_load_warehouse(**context):
    from pipelines.extract import extract_all
    from pipelines.transform import transform_all
    from pipelines.load import load_all
    raw_datasets = extract_all()
    clean_op, star_schema, dq = transform_all(raw_datasets)
    load_all(clean_op, star_schema)
    return "Warehouse tables populated."

def task_demand_forecasting(**context):
    from forecasting.demand_forecast import generate_demand_forecasts
    metrics = generate_demand_forecasts(horizon_days=30)
    return f"Forecast generated with MAE: {metrics['metrics']['mae']}"

if DAG is not None:
    with DAG(
        dag_id="demandiq_daily_demand_etl",
        default_args=default_args,
        description="Daily Batch ETL, Validation, Star Schema Loading & Demand Forecasting",
        schedule_interval="@daily",
        catchup=False,
        max_active_runs=1,
        tags=["demandiq", "etl", "star_schema", "forecasting"],
    ) as dag:

        start_pipeline = EmptyOperator(task_id="start_pipeline")

        extract_sources = PythonOperator(
            task_id="extract_sources_and_api",
            python_callable=task_extract_sources
        )

        clean_and_validate = PythonOperator(
            task_id="clean_and_validate_data",
            python_callable=task_clean_validate
        )

        load_warehouse = PythonOperator(
            task_id="load_star_schema_warehouse",
            python_callable=task_load_warehouse
        )

        run_forecasting = PythonOperator(
            task_id="run_demand_forecasting",
            python_callable=task_demand_forecasting
        )

        end_pipeline = EmptyOperator(task_id="end_pipeline")

        # Define Task Dependencies
        start_pipeline >> extract_sources >> clean_and_validate >> load_warehouse >> run_forecasting >> end_pipeline
