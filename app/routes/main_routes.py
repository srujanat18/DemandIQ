"""
Flask Blueprint & API Routes for DemandIQ
Serves analytical dashboards and provides JSON endpoints for charts and pipeline operations.
"""
import logging
from flask import Blueprint, render_template, jsonify, request
from sqlalchemy import text
import pandas as pd
from database.db_connection import get_engine
from monitoring.pipeline_logger import get_recent_pipeline_logs
from validation.data_quality import get_latest_dq_report
from pipelines.main import run_full_pipeline
from pipelines.incremental_load import run_incremental_load, get_current_watermark
from forecasting.demand_forecast import generate_demand_forecasts, get_forecast_summary_data

logger = logging.getLogger("DemandIQ.Web")
main_bp = Blueprint("main", __name__)

def fetch_kpis():
    """Calculates top-level KPI metrics directly from database."""
    engine = get_engine()
    kpis = {
        "total_revenue": 0.0,
        "total_units": 0,
        "total_products": 0,
        "total_customers": 0,
        "last_pipeline_status": "READY",
        "last_pipeline_time": "Never"
    }
    try:
        with engine.connect() as conn:
            sales_row = conn.execute(text("SELECT COALESCE(SUM(total_amount), 0), COALESCE(SUM(quantity), 0) FROM sales")).fetchone()
            if sales_row:
                kpis["total_revenue"] = float(sales_row[0])
                kpis["total_units"] = int(sales_row[1])

            prods_row = conn.execute(text("SELECT COUNT(*) FROM products")).fetchone()
            if prods_row:
                kpis["total_products"] = int(prods_row[0])

            custs_row = conn.execute(text("SELECT COUNT(*) FROM customers")).fetchone()
            if custs_row:
                kpis["total_customers"] = int(custs_row[0])

            log_row = conn.execute(text("SELECT status, start_time FROM pipeline_logs ORDER BY start_time DESC LIMIT 1")).fetchone()
            if log_row:
                kpis["last_pipeline_status"] = str(log_row[0])
                kpis["last_pipeline_time"] = str(log_row[1])
    except Exception as e:
        logger.error(f"Error calculating KPIs: {e}")

    return kpis

# ----------------- HTML PAGE ROUTES ----------------- #

@main_bp.route("/")
def index():
    kpis = fetch_kpis()
    engine = get_engine()

    # Fetch top 5 products
    top_products = []
    try:
        with engine.connect() as conn:
            df_top = pd.read_sql_query(text("SELECT * FROM v_top_selling_products LIMIT 5"), conn)
            top_products = df_top.to_dict(orient="records")
    except Exception:
        pass

    # Recent logs
    recent_logs = get_recent_pipeline_logs(limit=5)
    dq_report = get_latest_dq_report()

    return render_template(
        "index.html", 
        kpis=kpis, 
        top_products=top_products, 
        recent_logs=recent_logs,
        dq_report=dq_report,
        page="overview"
    )

@main_bp.route("/pipelines")
def pipelines_page():
    kpis = fetch_kpis()
    logs = get_recent_pipeline_logs(limit=50)
    watermark = get_current_watermark()
    dq_report = get_latest_dq_report()
    return render_template(
        "pipelines.html", 
        kpis=kpis, 
        logs=logs, 
        watermark=watermark, 
        dq_report=dq_report,
        page="pipelines"
    )

@main_bp.route("/analytics")
def analytics_page():
    engine = get_engine()
    monthly = []
    categories = []
    regions = []
    daily = []
    try:
        with engine.connect() as conn:
            monthly = pd.read_sql_query(text("SELECT * FROM v_monthly_sales_summary"), conn).to_dict(orient="records")
            categories = pd.read_sql_query(text("SELECT * FROM v_category_sales"), conn).to_dict(orient="records")
            regions = pd.read_sql_query(text("SELECT * FROM v_region_sales"), conn).to_dict(orient="records")
            daily = pd.read_sql_query(text("SELECT * FROM v_daily_sales_summary ORDER BY transaction_date DESC LIMIT 30"), conn).to_dict(orient="records")
    except Exception as e:
        logger.error(f"Error fetching analytics data: {e}")

    return render_template(
        "analytics.html",
        monthly=monthly,
        categories=categories,
        regions=regions,
        daily=daily,
        page="analytics"
    )

@main_bp.route("/forecasting")
def forecasting_page():
    engine = get_engine()
    inventory_risks = []
    try:
        with engine.connect() as conn:
            inventory_risks = pd.read_sql_query(text("SELECT * FROM v_inventory_demand_risk"), conn).to_dict(orient="records")
    except Exception as e:
        logger.error(f"Error fetching inventory risks: {e}")

    forecast_meta = generate_demand_forecasts(30)
    return render_template(
        "forecasting.html",
        inventory_risks=inventory_risks,
        metrics=forecast_meta.get("metrics", {}),
        top_demanded=forecast_meta.get("top_demanded", []),
        low_demanded=forecast_meta.get("low_demanded", []),
        page="forecasting"
    )

@main_bp.route("/quality")
def quality_page():
    dq_report = get_latest_dq_report()
    return render_template("quality.html", dq_report=dq_report, page="quality")

# ----------------- JSON API ENDPOINTS ----------------- #

@main_bp.route("/api/charts/monthly")
def api_chart_monthly():
    engine = get_engine()
    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(text("SELECT sales_month, total_revenue, total_units_sold FROM v_monthly_sales_summary ORDER BY sales_month ASC"), conn)
            return jsonify({
                "labels": df["sales_month"].tolist(),
                "revenue": df["total_revenue"].tolist(),
                "units": df["total_units_sold"].tolist()
            })
    except Exception as e:
        return jsonify({"error": str(e), "labels": [], "revenue": [], "units": []})

@main_bp.route("/api/charts/categories")
def api_chart_categories():
    engine = get_engine()
    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(text("SELECT category_name, total_revenue, units_sold FROM v_category_sales ORDER BY total_revenue DESC"), conn)
            return jsonify({
                "labels": df["category_name"].tolist(),
                "revenue": df["total_revenue"].tolist(),
                "units": df["units_sold"].tolist()
            })
    except Exception as e:
        return jsonify({"error": str(e), "labels": [], "revenue": [], "units": []})

@main_bp.route("/api/charts/forecast")
def api_chart_forecast():
    summary = get_forecast_summary_data()
    return jsonify(summary)

@main_bp.route("/api/pipeline/run-full", methods=["POST"])
def api_run_full_pipeline():
    try:
        res = run_full_pipeline()
        return jsonify({"success": True, "data": res})
    except Exception as e:
        logger.error(f"Manual full pipeline run failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@main_bp.route("/api/pipeline/run-incremental", methods=["POST"])
def api_run_incremental():
    try:
        res = run_incremental_load()
        return jsonify({"success": True, "data": res})
    except Exception as e:
        logger.error(f"Incremental pipeline run failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
