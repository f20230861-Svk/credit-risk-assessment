"""
Database connection and logging for credit risk assessments.
Every call to /assess-risk is logged to Postgres as an audit trail.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    """Creates the assessments table if it doesn't already exist."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS assessments (
            id SERIAL PRIMARY KEY,
            txn_regularity FLOAT,
            utility_payment_score FLOAT,
            avg_monthly_inflow FLOAT,
            mobile_usage_stability FLOAT,
            social_signal_score FLOAT,
            final_score FLOAT,
            risk_band TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def log_assessment(inputs: dict, result: dict):
    """Saves one assessment (inputs + result) to the database."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO assessments (
            txn_regularity, utility_payment_score, avg_monthly_inflow,
            mobile_usage_stability, social_signal_score,
            final_score, risk_band
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        inputs["txn_regularity"],
        inputs["utility_payment_score"],
        inputs["avg_monthly_inflow"],
        inputs["mobile_usage_stability"],
        inputs["social_signal_score"],
        result["final_score"],
        result["risk_band"],
    ))
    conn.commit()
    cur.close()
    conn.close()


def get_recent_assessments(limit: int = 20):
    """Fetches the most recent assessments, for a simple history view."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM assessments
        ORDER BY created_at DESC
        LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows