"""
Flask Blueprint & Interactive API Routes for DemandIQ
Provides both:
1. Manufacturer & Factory Operations (Simple, Actionable, Visual, Zero Jargon)
2. Data Engineering Console (Pipelines, Staging, Star Schema, Watermarks, Logs)
"""
import io
import csv
import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template, jsonify, request, Response
from sqlalchemy import text
import pandas as pd
from database.db_connection import get_engine
from monitoring.pipeline_logger import get_recent_pipeline_logs
from validation.data_quality import get_latest_dq_report, validate_and_clean_sales
from pipelines.main import run_full_pipeline
from pipelines.incremental_load import run_incremental_load, get_current_watermark, save_watermark
from forecasting.demand_forecast import generate_demand_forecasts, get_forecast_summary_data
import config

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
        "urgent_restock_count": 0,
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

            # Check urgent restock items (stock <= reorder_level)
            urgent_row = conn.execute(text("SELECT COUNT(*) FROM products WHERE stock_quantity <= reorder_level")).fetchone()
            if urgent_row:
                kpis["urgent_restock_count"] = int(urgent_row[0])

            log_row = conn.execute(text("SELECT status, start_time FROM pipeline_logs ORDER BY start_time DESC LIMIT 1")).fetchone()
            if log_row:
                kpis["last_pipeline_status"] = str(log_row[0])
                kpis["last_pipeline_time"] = str(log_row[1])
    except Exception as e:
        logger.error(f"Error calculating KPIs: {e}")

    return kpis

def fetch_production_planning():
    """Calculates plain-English manufacturing schedule and inventory urgency."""
    engine = get_engine()
    schedule = []
    try:
        query = text("""
            SELECT 
                p.product_id,
                p.product_name,
                c.category_name,
                p.stock_quantity,
                p.reorder_level,
                p.cost_price,
                p.list_price,
                COALESCE(f.predicted_30d, 30) AS predicted_30d_demand
            FROM products p
            JOIN categories c ON p.category_id = c.category_id
            LEFT JOIN (
                SELECT product_id, SUM(predicted_demand) AS predicted_30d
                FROM forecasts
                GROUP BY product_id
            ) f ON p.product_id = f.product_id
            ORDER BY (p.stock_quantity - COALESCE(f.predicted_30d, 30)) ASC
        """)
        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn)

        for _, row in df.iterrows():
            stock = int(row["stock_quantity"])
            demand_30d = int(row["predicted_30d_demand"])
            reorder = int(row["reorder_level"])
            daily_burn = max(0.5, demand_30d / 30.0)
            days_left = int(round(stock / daily_burn))

            # Recommended production to cover 30 days + safety stock
            needed_production = max(0, (demand_30d + reorder) - stock)

            if stock <= reorder or days_left <= 10:
                urgency = "CRITICAL"
                badge_class = "danger"
                action_text = f"🚨 URGENT: Produce {needed_production} units (Runs out in ~{days_left} days)"
            elif days_left <= 20:
                urgency = "WARNING"
                badge_class = "warning"
                action_text = f"⚠️ SCHEDULE: Produce {needed_production} units (Runs out in ~{days_left} days)"
            elif days_left > 60:
                urgency = "OVERSTOCKED"
                badge_class = "info"
                action_text = f"🛑 PAUSE: {days_left} days of stock already available"
            else:
                urgency = "HEALTHY"
                badge_class = "success"
                action_text = f"✅ OPTIMAL: Stock healthy for {days_left} days"

            schedule.append({
                "product_id": int(row["product_id"]),
                "product_name": str(row["product_name"]),
                "category_name": str(row["category_name"]),
                "stock_quantity": stock,
                "reorder_level": reorder,
                "cost_price": float(row["cost_price"]),
                "list_price": float(row["list_price"]),
                "predicted_30d_demand": demand_30d,
                "days_left": days_left,
                "needed_production": needed_production,
                "urgency": urgency,
                "badge_class": badge_class,
                "action_text": action_text
            })
    except Exception as e:
        logger.error(f"Error fetching production planning: {e}")

    return schedule

# ----------------- HTML PAGE ROUTES ----------------- #

@main_bp.route("/")
def index():
    kpis = fetch_kpis()
    production_schedule = fetch_production_planning()
    recent_logs = get_recent_pipeline_logs(limit=5)
    dq_report = get_latest_dq_report()

    # Split into urgent action items and healthy items
    urgent_items = [p for p in production_schedule if p["urgency"] in ["CRITICAL", "WARNING"]]
    healthy_items = [p for p in production_schedule if p["urgency"] not in ["CRITICAL", "WARNING"]]

    return render_template(
        "index.html",
        kpis=kpis,
        production_schedule=production_schedule,
        urgent_items=urgent_items,
        healthy_items=healthy_items,
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
    production_schedule = fetch_production_planning()
    forecast_meta = generate_demand_forecasts(30)
    return render_template(
        "forecasting.html",
        production_schedule=production_schedule,
        metrics=forecast_meta.get("metrics", {}),
        top_demanded=forecast_meta.get("top_demanded", []),
        low_demanded=forecast_meta.get("low_demanded", []),
        page="forecasting"
    )

@main_bp.route("/quality")
def quality_page():
    dq_report = get_latest_dq_report()
    return render_template("quality.html", dq_report=dq_report, page="quality")

# ----------------- INTERACTIVE MANUFACTURER API ENDPOINTS ----------------- #

@main_bp.route("/api/products/list")
def api_products_list():
    """Returns list of products for dropdown selection."""
    engine = get_engine()
    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(text("SELECT product_id, product_name, stock_quantity, reorder_level FROM products ORDER BY product_name"), conn)
            return jsonify({"success": True, "products": df.to_dict(orient="records")})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@main_bp.route("/api/products/details/<int:product_id>")
def api_product_details(product_id: int):
    """Returns detailed manufacturing telemetry and charts for a specific product."""
    engine = get_engine()
    try:
        with engine.connect() as conn:
            prod_row = conn.execute(
                text("""
                    SELECT p.product_id, p.product_name, c.category_name, p.stock_quantity, 
                           p.reorder_level, p.cost_price, p.list_price
                    FROM products p
                    JOIN categories c ON p.category_id = c.category_id
                    WHERE p.product_id = :pid
                """),
                {"pid": product_id}
            ).fetchone()

            if not prod_row:
                return jsonify({"success": False, "error": "Product not found"}), 404

            # Fetch daily sales history (last 30 days)
            df_hist = pd.read_sql_query(
                text("""
                    SELECT transaction_date, SUM(quantity) as units_sold
                    FROM sales
                    WHERE product_id = :pid
                    GROUP BY transaction_date
                    ORDER BY transaction_date DESC
                    LIMIT 30
                """),
                conn,
                params={"pid": product_id}
            )
            df_hist = df_hist.sort_values("transaction_date")

            # Fetch future 30-day forecast
            df_fc = pd.read_sql_query(
                text("""
                    SELECT forecast_date, predicted_demand
                    FROM forecasts
                    WHERE product_id = :pid
                    ORDER BY forecast_date ASC
                """),
                conn,
                params={"pid": product_id}
            )

        stock = int(prod_row[3])
        reorder = int(prod_row[4])
        forecast_30d = int(df_fc["predicted_demand"].sum()) if not df_fc.empty else 30
        daily_rate = max(0.5, forecast_30d / 30.0)
        days_remaining = int(round(stock / daily_rate))
        recommended_build = max(0, (forecast_30d + reorder) - stock)

        return jsonify({
            "success": True,
            "product": {
                "id": prod_row[0],
                "name": prod_row[1],
                "category": prod_row[2],
                "stock": stock,
                "reorder_level": reorder,
                "cost_price": float(prod_row[5]),
                "list_price": float(prod_row[6]),
                "forecast_30d": forecast_30d,
                "days_remaining": days_remaining,
                "recommended_build": recommended_build
            },
            "history": {
                "dates": df_hist["transaction_date"].tolist(),
                "values": df_hist["units_sold"].tolist()
            },
            "forecast": {
                "dates": df_fc["forecast_date"].tolist(),
                "values": df_fc["predicted_demand"].tolist()
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@main_bp.route("/api/simulator/calculate", methods=["POST"])
def api_simulator():
    """Simulates what-if scenarios: 'If I produce X more units and demand shifts by Y%'."""
    data = request.get_json() or {}
    product_id = int(data.get("product_id", 101))
    additional_production = int(data.get("additional_production", 0))
    demand_change_pct = float(data.get("demand_change_pct", 0.0))

    engine = get_engine()
    try:
        with engine.connect() as conn:
            prod_row = conn.execute(
                text("SELECT product_name, stock_quantity, reorder_level FROM products WHERE product_id = :pid"),
                {"pid": product_id}
            ).fetchone()

            fc_sum = conn.execute(
                text("SELECT COALESCE(SUM(predicted_demand), 30) FROM forecasts WHERE product_id = :pid"),
                {"pid": product_id}
            ).fetchone()

        stock = int(prod_row[1])
        base_demand = int(fc_sum[0])
        product_name = prod_row[0]

        # Scenario calculations
        adjusted_demand = max(1, int(round(base_demand * (1.0 + (demand_change_pct / 100.0)))))
        total_available = stock + additional_production
        daily_rate = max(0.5, adjusted_demand / 30.0)
        days_remaining = int(round(total_available / daily_rate))
        net_balance = total_available - adjusted_demand

        if net_balance < 0:
            status = "DEFICIT"
            status_class = "danger"
            message = f"🚨 Stockout Risk! You will run out in ~{days_remaining} days (Deficit of {abs(net_balance)} units). Increase production!"
        elif net_balance < 15:
            status = "TIGHT"
            status_class = "warning"
            message = f"⚠️ Low Buffer: Stock will last ~{days_remaining} days. Very close to reorder threshold."
        else:
            status = "SAFE"
            status_class = "success"
            message = f"✅ Excellent: Stock will safely last ~{days_remaining} days with a healthy surplus of {net_balance} units."

        return jsonify({
            "success": True,
            "product_name": product_name,
            "starting_stock": stock,
            "additional_production": additional_production,
            "total_available": total_available,
            "adjusted_demand": adjusted_demand,
            "net_balance": net_balance,
            "days_remaining": days_remaining,
            "status": status,
            "status_class": status_class,
            "message": message
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@main_bp.route("/api/upload/sales-data", methods=["POST"])
def api_upload_sales_data():
    """Allows users to drag & drop or upload a CSV file with automatic cleaning and immediate analytics update."""
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "error": "No file selected"}), 400

    try:
        df_uploaded = pd.read_csv(file)
        
        # Verify required columns exist or map them
        required_cols = {"sale_id", "transaction_date", "product_id", "quantity", "unit_price"}
        if not required_cols.issubset(set(df_uploaded.columns)):
            return jsonify({
                "success": False, 
                "error": f"CSV must contain at least: {', '.join(required_cols)}"
            }), 400

        # Fill default columns if missing
        if "customer_id" not in df_uploaded.columns:
            df_uploaded["customer_id"] = 1001
        if "discount_pct" not in df_uploaded.columns:
            df_uploaded["discount_pct"] = 0.0
        if "payment_method" not in df_uploaded.columns:
            df_uploaded["payment_method"] = "Credit Card"
        if "channel" not in df_uploaded.columns:
            df_uploaded["channel"] = "Online"

        # Fetch active products & customers
        engine = get_engine()
        with engine.connect() as conn:
            prods = set(pd.read_sql_query(text("SELECT product_id FROM products"), conn)["product_id"])
            custs = set(pd.read_sql_query(text("SELECT customer_id FROM customers"), conn)["customer_id"])

        # Run Data Quality Validation
        clean_delta, dq_report = validate_and_clean_sales(
            df_uploaded,
            valid_product_ids=prods,
            valid_customer_ids=custs
        )

        if clean_delta.empty:
            return jsonify({
                "success": False,
                "error": "All uploaded records failed validation checks (negative quantities or invalid product IDs)."
            }), 400

        # Append to sales table
        with engine.begin() as conn:
            clean_delta.to_sql("sales", conn, if_exists="append", index=False)

        # Update high-watermark
        new_max_id = int(clean_delta["sale_id"].max())
        new_max_date = str(clean_delta["transaction_date"].max())
        save_watermark(new_max_id, new_max_date)

        # Regenerate demand forecasts
        generate_demand_forecasts(30)

        return jsonify({
            "success": True,
            "message": f"Successfully processed {len(clean_delta)} new sales records!",
            "records_loaded": len(clean_delta),
            "duplicates_removed": dq_report.duplicates_removed,
            "invalid_rejected": dq_report.negative_quantities_rejected + dq_report.invalid_prices_rejected + dq_report.foreign_key_violations_rejected,
            "acceptance_rate": f"{dq_report.acceptance_rate_pct}%"
        })
    except Exception as e:
        logger.error(f"File upload error: {e}")
        return jsonify({"success": False, "error": f"Error parsing CSV file: {str(e)}"}), 500

@main_bp.route("/api/export/production-schedule")
def api_export_schedule():
    """Generates and downloads a clean, printable CSV file of the manufacturing schedule."""
    schedule = fetch_production_planning()
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "Product ID", "Product Name", "Category", "Current Stock", 
        "Reorder Level", "30-Day Demand Forecast", "Days Stock Left", 
        "Recommended Units to Manufacture", "Urgency Status"
    ])

    for item in schedule:
        writer.writerow([
            item["product_id"],
            item["product_name"],
            item["category_name"],
            item["stock_quantity"],
            item["reorder_level"],
            item["predicted_30d_demand"],
            item["days_left"],
            item["needed_production"],
            item["urgency"]
        ])

    csv_data = output.getvalue()
    today_str = datetime.utcnow().strftime("%Y%m%d")
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=DemandIQ_Production_Schedule_{today_str}.csv"}
    )

# ----------------- STANDARD CHARTS & PIPELINE APIS ----------------- #

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
