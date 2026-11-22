import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
SAMPLE_DATA_DIR = DATA_DIR / "sample"
DATABASE_DIR = BASE_DIR / "database"

# Ensure directories exist
for d in [RAW_DATA_DIR, PROCESSED_DATA_DIR, SAMPLE_DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Load environment variables
load_dotenv(BASE_DIR / ".env")

# Database Configuration
# Supports both SQLite (zero-config local default) and MySQL
DB_TYPE = os.getenv("DB_TYPE", "sqlite").lower()

MYSQL_HOST = os.getenv("DB_HOST", "localhost")
MYSQL_PORT = int(os.getenv("DB_PORT", 3306))
MYSQL_USER = os.getenv("DB_USER", "root")
MYSQL_PASSWORD = os.getenv("DB_PASSWORD", "")
MYSQL_DATABASE = os.getenv("DB_NAME", "demandiq")

SQLITE_PATH = os.getenv("SQLITE_PATH", str(DATABASE_DIR / "demandiq.db"))

# Open-Meteo Weather API Config (Free, public, no API key required)
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_LATITUDE = float(os.getenv("WEATHER_LAT", "40.7128"))   # Default: New York
WEATHER_LONGITUDE = float(os.getenv("WEATHER_LON", "-74.0060"))

# Pipeline Watermark File for Incremental Loading
WATERMARK_FILE = DATA_DIR / "last_watermark.json"

# AWS Configuration (Optional / Integration)
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "demandiq-data-lake-raw")
