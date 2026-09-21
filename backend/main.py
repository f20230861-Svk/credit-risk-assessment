"""
FastAPI server exposing the credit risk model as an API.

  GET  /             health check (open, used by Render to monitor the service)
  POST /login        exchange a username and password for a signed token
  POST /assess-risk  score an applicant and log it to Postgres (token required)
  GET  /history      recent assessments (token required)
  GET  /fairness-report  outcomes by type of area, for auditing (token required)

Secrets are read from environment variables and never written in the code:
  AUTH_USERNAME, AUTH_PASSWORD  the one account allowed to sign in
  JWT_SECRET                    key used to sign tokens (long and random)
  ALLOWED_ORIGINS               optional, comma-separated list of websites
                                allowed to call this API (default: any)
  GEMINI_API_KEY, GEMINI_MODEL  optional, turn on the AI-written explanation
                                (see explain.py)
"""

import copy
import hmac
import os
import time
from typing import Literal

import jwt
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, model_validator

from model import compute_risk_score
from database import init_db, log_assessment, get_recent_assessments, get_fairness_report
from explain import generate_explanation

TOKEN_LIFETIME_SECONDS = 12 * 60 * 60  # a signed-in session lasts 12 hours

app = FastAPI(title="Credit Risk Assessment API")

# Requests carry a bearer token, not cookies, so another website cannot ride on
# a visitor's session. Set ALLOWED_ORIGINS in production to limit callers anyway.
allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


Vehicle = Literal["none", "cycle", "two_wheeler", "second_hand_car", "car"]
AreaType = Literal["urban", "semi_urban", "rural"]


class ApplicantData(BaseModel):
    """Facts about a household and the loan it asks for. Money is in rupees a month unless stated."""

    monthly_income: float = Field(..., ge=0, le=10_000_000)
    lowest_month_income: float = Field(..., ge=0, le=10_000_000)
    household_size: int = Field(..., ge=1, le=20)
    household_expenses: float = Field(..., ge=0, le=10_000_000)
    existing_loan_payments: float = Field(..., ge=0, le=10_000_000)
    active_loans: int = Field(..., ge=0, le=20)
    loan_amount: float = Field(..., ge=0, le=10_000_000)
    tenure_months: int = Field(..., ge=1, le=120)
    annual_rate_percent: float = Field(..., ge=0, le=60)
    bills_on_time: int = Field(..., ge=0, le=12)
    failed_payments: int = Field(..., ge=0, le=50)
    avg_balance: float = Field(..., ge=0, le=100_000_000)
    months_in_work: int = Field(..., ge=0, le=600)
    vehicle: Vehicle
    area_type: AreaType  # kept for the fairness audit only, never used in the score

    @model_validator(mode="after")
    def lowest_month_cannot_beat_the_average(self):
        if self.lowest_month_income > self.monthly_income:
            raise ValueError("lowest_month_income cannot be higher than monthly_income")
        return self


class LoginRequest(BaseModel):
    username: str
    password: str


# ---------- authentication ----------

bearer_scheme = HTTPBearer(auto_error=False)


def get_secret(name: str) -> str:
    """Reads a required setting. Fails closed if it is missing."""
    value = os.getenv(name)
    if not value:
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured on the server.",
        )
    return value


def require_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """Dependency that lets a request through only with a valid, unexpired token."""
    challenge = {"WWW-Authenticate": "Bearer"}

    if credentials is None:
        raise HTTPException(status_code=401, detail="Sign in to continue.", headers=challenge)

    try:
        payload = jwt.decode(
            credentials.credentials,
            get_secret("JWT_SECRET"),
            algorithms=["HS256"],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Your session has expired. Sign in again.", headers=challenge)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token. Sign in again.", headers=challenge)

    return payload["sub"]


@app.post("/login")
def login(body: LoginRequest):
    expected_user = get_secret("AUTH_USERNAME")
    expected_password = get_secret("AUTH_PASSWORD")

    # compare_digest takes the same time however many characters match,
    # so response timing gives nothing away.
    user_ok = hmac.compare_digest(body.username.encode(), expected_user.encode())
    password_ok = hmac.compare_digest(body.password.encode(), expected_password.encode())

    if not (user_ok and password_ok):
        raise HTTPException(status_code=401, detail="Incorrect username or password.")

    now = int(time.time())
    token = jwt.encode(
        {"sub": body.username, "iat": now, "exp": now + TOKEN_LIFETIME_SECONDS},
        get_secret("JWT_SECRET"),
        algorithm="HS256",
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": TOKEN_LIFETIME_SECONDS,
    }


# ---------- endpoints ----------

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Credit Risk Assessment API is running"}


@app.post("/assess-risk")
def assess_risk(data: ApplicantData, user: str = Depends(require_user)):
    inputs = data.model_dump()
    area_type = inputs.pop("area_type")   # audit only: it never reaches the scorecard
    result = compute_risk_score(**inputs)
    log_assessment({**inputs, "area_type": area_type}, result)

    # The score above is final. The AI explanation is an optional extra: it is
    # None when the AI is off or unavailable, and the app then shows its
    # built-in explanation instead.
    result["ai_explanation"] = generate_explanation(copy.deepcopy(result))
    return result


@app.get("/fairness-report")
def fairness_report(user: str = Depends(require_user)):
    return get_fairness_report()


@app.get("/history")
def history(limit: int = Query(20, ge=1, le=100), user: str = Depends(require_user)):
    return get_recent_assessments(limit)
