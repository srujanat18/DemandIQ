from sqlalchemy import text
from database.db_connection import init_db, get_engine
from pipelines.extract import extract_all
from pipelines.transform import transform_all
from pipelines.load import load_all
from pipelines.incremental_load import get_current_watermark, run_incremental_load
from forecasting.demand_forecast import generate_demand_forecasts

def test_database_initialization():
    """Verify that schema initialization creates required tables without errors."""
    init_db()
    engine = get_engine()
    with engine.connect() as conn:
        # Check that core tables exist
        for tbl in ["products", "categories", "customers", "sales", "weather", "pipeline_logs", "dim_date", "fact_sales"]:
            res = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
            assert res is not None

def test_full_pipeline_flow():
    """Verify full end-to-end extraction, transformation, star schema generation, and load."""
    raw = extract_all()
    assert "sales" in raw
    assert "products" in raw
    assert "weather" in raw

    clean_op, star_schema, dq = transform_all(raw)
    assert dq.final_valid_records > 0
    assert len(star_schema["fact_sales"]) == dq.final_valid_records
    assert len(star_schema["dim_date"]) > 0

    load_all(clean_op, star_schema)

    # Verify forecasting works on loaded data
    forecast_meta = generate_demand_forecasts(horizon_days=7)
    assert forecast_meta["forecasts_count"] > 0
    assert "mae" in forecast_meta["metrics"]

def test_watermark_incremental_pipeline():
    """Verify that incremental load tracks watermarks correctly."""
    watermark_before = get_current_watermark()
    assert "last_processed_sale_id" in watermark_before
    
    # Run incremental load
    res = run_incremental_load()
    assert res["status"] in ["SUCCESS", "UP_TO_DATE"]
