"""
FastAPI server exposing the credit risk model as an API.

  GET  /             health check (open, used by Render to monitor the service)
  POST /login        exchange a username and password for a signed token
  POST /assess-risk  score an applicant and log it to Postgres (token required)
  GET  /history      recent assessments (token required)

Secrets are read from environment variables and never written in the code:
  AUTH_USERNAME, AUTH_PASSWORD  the one account allowed to sign in
  JWT_SECRET                    key used to sign tokens (long and random)
  ALLOWED_ORIGINS               optional, comma-separated list of websites
                                allowed to call this API (default: any)
"""

import hmac
import os
import time

import jwt
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from model import compute_risk_score
from database import init_db, log_assessment, get_recent_assessments

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


class ApplicantData(BaseModel):
    txn_regularity: float = Field(..., ge=0, le=100)
    utility_payment_score: float = Field(..., ge=0, le=100)
    avg_monthly_inflow: float = Field(..., ge=0)
    mobile_usage_stability: float = Field(..., ge=0, le=100)
    social_signal_score: float = Field(..., ge=0, le=100)


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
def history(limit: int = Query(20, ge=1, le=100), user: str = Depends(require_user)):
    return get_recent_assessments(limit)
