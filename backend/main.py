"""
FastAPI server exposing the credit risk model as an API.

Endpoints:
  GET  /                -> health check
  POST /assess-risk     -> takes applicant signals, returns risk score
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from model import compute_risk_score

app = FastAPI(title="Credit Risk Assessment API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ApplicantData(BaseModel):
    txn_regularity: float = Field(..., ge=0, le=100, description="0-100 score of transaction consistency")
    utility_payment_score: float = Field(..., ge=0, le=100, description="0-100, % of bills paid on time")
    avg_monthly_inflow: float = Field(..., ge=0, description="Average monthly money received, in INR")
    mobile_usage_stability: float = Field(..., ge=0, le=100, description="0-100 mobile usage consistency")
    social_signal_score: float = Field(..., ge=0, le=100, description="0-100 digital footprint proxy")


@app.get("/")
def health_check():
    return {"status": "ok", "message": "Credit Risk Assessment API is running"}


@app.post("/assess-risk")
def assess_risk(data: ApplicantData):
    result = compute_risk_score(
        txn_regularity=data.txn_regularity,
        utility_payment_score=data.utility_payment_score,
        avg_monthly_inflow=data.avg_monthly_inflow,
        mobile_usage_stability=data.mobile_usage_stability,
        social_signal_score=data.social_signal_score,
    )
    return result