"""
Pipeline Monitoring & Observability Module for DemandIQ
Logs pipeline executions, runtimes, records processed, and failures to both standard logger and the database.
"""
import logging
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import text
from database.db_connection import get_engine
import config

# Configure python standard logger
LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("DemandIQ.Pipeline")

class PipelineRun:
    """Context manager and tracker for an individual ETL pipeline execution."""
    def __init__(self, pipeline_name: str):
        self.pipeline_name = pipeline_name
        self.pipeline_id = f"pipe_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self.start_time = datetime.utcnow()
        self.end_time: Optional[datetime] = None
        self.duration_seconds: float = 0.0
        self.records_processed: int = 0
        self.status: str = "RUNNING"
        self.error_message: Optional[str] = None

    def __enter__(self):
        logger.info(f"Starting pipeline '{self.pipeline_name}' [ID: {self.pipeline_id}]")
        self._record_start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = datetime.utcnow()
        self.duration_seconds = round((self.end_time - self.start_time).total_seconds(), 2)

        if exc_type is not None:
            self.status = "FAILED"
            self.error_message = f"{exc_type.__name__}: {str(exc_val)}"
            logger.error(f"Pipeline '{self.pipeline_name}' failed after {self.duration_seconds}s: {self.error_message}")
        else:
            if self.status != "FAILED":
                self.status = "SUCCESS"
            logger.info(f"Pipeline '{self.pipeline_name}' completed successfully in {self.duration_seconds}s. Records: {self.records_processed}")

        self._record_finish()
        # Suppress exception only if desired, but we let it propagate for pipeline callers
        return False

    def add_records(self, count: int):
        self.records_processed += count

    def set_failed(self, error_msg: str):
        self.status = "FAILED"
        self.error_message = error_msg

    def _record_start(self):
        """Insert initial running record into database."""
        engine = get_engine()
        query = text("""
            INSERT INTO pipeline_logs 
            (pipeline_id, pipeline_name, start_time, status, records_processed)
            VALUES (:pid, :name, :start, :status, :records)
        """)
        try:
            with engine.begin() as conn:
                conn.execute(query, {
                    "pid": self.pipeline_id,
                    "name": self.pipeline_name,
                    "start": self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "RUNNING",
                    "records": 0
                })
        except Exception as e:
            logger.warning(f"Could not write initial log to DB: {e}")

    def _record_finish(self):
        """Update finished state in database."""
        engine = get_engine()
        query = text("""
            UPDATE pipeline_logs 
            SET end_time = :end,
                duration_seconds = :duration,
                records_processed = :records,
                status = :status,
                error_message = :err
            WHERE pipeline_id = :pid
        """)
        try:
            with engine.begin() as conn:
                conn.execute(query, {
                    "end": self.end_time.strftime("%Y-%m-%d %H:%M:%S") if self.end_time else None,
                    "duration": self.duration_seconds,
                    "records": self.records_processed,
                    "status": self.status,
                    "err": self.error_message,
                    "pid": self.pipeline_id
                })
        except Exception as e:
            logger.warning(f"Could not update final log in DB: {e}")

def get_recent_pipeline_logs(limit: int = 20):
    """Fetches recent pipeline execution logs for dashboard and monitoring."""
    engine = get_engine()
    query = text("""
        SELECT pipeline_id, pipeline_name, start_time, end_time, duration_seconds,
               records_processed, status, error_message
        FROM pipeline_logs
        ORDER BY start_time DESC
        LIMIT :lim
    """)
    try:
        import pandas as pd
        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn, params={"lim": limit})
        return df.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Error fetching pipeline logs: {e}")
        return []
