"""
Database connection and logging for credit risk assessments.
Every call to /assess-risk is logged to Postgres as an audit trail.

The table is called assessments_v2 and keeps the inputs as one JSON document,
so the scorecard can gain or lose inputs without changing the table again.
"""

import os

import psycopg2
from psycopg2.extras import Json, RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    """Creates the assessments_v2 table if it doesn't already exist."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS assessments_v2 (
            id SERIAL PRIMARY KEY,
            inputs JSONB NOT NULL,
            final_score FLOAT NOT NULL,
            risk_band TEXT NOT NULL,
            overrides JSONB NOT NULL DEFAULT '[]',
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
        INSERT INTO assessments_v2 (inputs, final_score, risk_band, overrides)
        VALUES (%s, %s, %s, %s)
    """, (
        Json(inputs),
        result["final_score"],
        result["risk_band"],
        Json(result["overrides"]),
    ))
    conn.commit()
    cur.close()
    conn.close()


def get_recent_assessments(limit: int = 20):
    """Fetches the most recent assessments, for a simple history view."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, inputs, final_score, risk_band, overrides, created_at
        FROM assessments_v2
        ORDER BY created_at DESC
        LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows
