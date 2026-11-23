"""
Web Route and API Endpoint Tests for DemandIQ Dashboard
"""
import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_overview_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"DemandIQ" in response.data
    assert b"Production & Demand Command Center" in response.data

def test_pipelines_page_loads(client):
    response = client.get("/pipelines")
    assert response.status_code == 200
    assert b"Pipeline Automation" in response.data

def test_analytics_page_loads(client):
    response = client.get("/analytics")
    assert response.status_code == 200
    assert b"SQL Analytics" in response.data

def test_forecasting_page_loads(client):
    response = client.get("/forecasting")
    assert response.status_code == 200
    assert b"Demand Forecasting" in response.data

def test_quality_page_loads(client):
    response = client.get("/quality")
    assert response.status_code == 200
    assert b"Data Health" in response.data

def test_api_monthly_chart(client):
    response = client.get("/api/charts/monthly")
    assert response.status_code == 200
    json_data = response.get_json()
    assert "labels" in json_data
    assert "revenue" in json_data

def test_api_categories_chart(client):
    response = client.get("/api/charts/categories")
    assert response.status_code == 200
    json_data = response.get_json()
    assert "labels" in json_data
    assert "revenue" in json_data

def test_api_forecast_chart(client):
    response = client.get("/api/charts/forecast")
    assert response.status_code == 200
    json_data = response.get_json()
    assert "dates" in json_data
    assert "values" in json_data

def test_api_products_list(client):
    response = client.get("/api/products/list")
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["success"] is True
    assert len(json_data["products"]) > 0

def test_api_product_details(client):
    response = client.get("/api/products/details/101")
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["success"] is True
    assert "product" in json_data
    assert "forecast_30d" in json_data["product"]

def test_api_simulator_calculate(client):
    response = client.post("/api/simulator/calculate", json={
        "product_id": 101,
        "additional_production": 50,
        "demand_change_pct": 10.0
    })
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["success"] is True
    assert "days_remaining" in json_data
    assert "status" in json_data

def test_api_export_production_schedule(client):
    response = client.get("/api/export/production-schedule")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert b"Product ID,Product Name,Category" in response.data
