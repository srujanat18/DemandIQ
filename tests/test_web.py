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
    assert b"Executive Demand Intelligence Dashboard" in response.data

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
    assert b"Data Quality" in response.data

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
