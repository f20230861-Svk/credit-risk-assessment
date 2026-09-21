"""
FastAPI server exposing the credit risk model as an API.
Logs every assessment to Postgres for audit/history purposes.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from model import compute_risk_score
from database import init_db, log_assessment, get_recent_assessments

app = FastAPI(title="Credit Risk Assessment API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


class ApplicantData(BaseModel):
    txn_regularity: float = Field(..., ge=0, le=100)
    utility_payment_score: float = Field(..., ge=0, le=100)
    avg_monthly_inflow: float = Field(..., ge=0)
    mobile_usage_stability: float = Field(..., ge=0, le=100)
    social_signal_score: float = Field(..., ge=0, le=100)


@app.get("/")
def health_check():
    return {"status": "ok", "message": "Credit Risk Assessment API is running"}


@app.post("/assess-risk")
def assess_risk(data: ApplicantData):
    inputs = data.model_dump()
    result = compute_risk_score(
        txn_regularity=data.txn_regularity,
        utility_payment_score=data.utility_payment_score,
        avg_monthly_inflow=data.avg_monthly_inflow,
        mobile_usage_stability=data.mobile_usage_stability,
        social_signal_score=data.social_signal_score,
    )
    log_assessment(inputs, result)
    return result


@app.get("/history")
def history(limit: int = 20):
    return get_recent_assessments(limit)
