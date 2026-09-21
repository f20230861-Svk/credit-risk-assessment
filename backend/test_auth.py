"""Tests for sign-in and token checks (backend/main.py).

The database is replaced with stand-ins, so these tests never touch Neon.
"""

import time

import jwt
import pytest
from fastapi.testclient import TestClient

import main

SECRET = "test-secret-that-is-long-enough-for-hs256-signing"

VALID_INPUTS = {
    "txn_regularity": 85,
    "utility_payment_score": 90,
    "avg_monthly_inflow": 42000,
    "mobile_usage_stability": 80,
    "social_signal_score": 70,
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AUTH_USERNAME", "analyst")
    monkeypatch.setenv("AUTH_PASSWORD", "correct-horse-battery")
    monkeypatch.setenv("JWT_SECRET", SECRET)

    saved = []
    monkeypatch.setattr(main, "log_assessment", lambda inputs, result: saved.append((inputs, result)))
    monkeypatch.setattr(main, "get_recent_assessments", lambda limit: [])

    # Not used as a context manager, so the startup hook (init_db) does not run.
    test_client = TestClient(main.app)
    test_client.saved = saved
    return test_client


def sign_in(client):
    response = client.post("/login", json={"username": "analyst", "password": "correct-horse-battery"})
    assert response.status_code == 200
    return response.json()["access_token"]


def bearer(token):
    return {"Authorization": "Bearer " + token}


def test_health_check_stays_open(client):
    assert client.get("/").status_code == 200


def test_login_with_correct_details_returns_a_token(client):
    response = client.post("/login", json={"username": "analyst", "password": "correct-horse-battery"})
    body = response.json()
    assert response.status_code == 200
    assert body["token_type"] == "bearer"
    assert jwt.decode(body["access_token"], SECRET, algorithms=["HS256"])["sub"] == "analyst"


@pytest.mark.parametrize(
    "username, password",
    [("analyst", "wrong-password"), ("someone-else", "correct-horse-battery"), ("", "")],
)
def test_login_rejects_wrong_details(client, username, password):
    response = client.post("/login", json={"username": username, "password": password})
    assert response.status_code == 401


def test_assess_risk_needs_a_token(client):
    response = client.post("/assess-risk", json=VALID_INPUTS)
    assert response.status_code == 401
    assert client.saved == []  # nothing was written


def test_history_needs_a_token(client):
    assert client.get("/history").status_code == 401


def test_signed_in_user_can_assess_risk(client):
    token = sign_in(client)
    response = client.post("/assess-risk", json=VALID_INPUTS, headers=bearer(token))
    assert response.status_code == 200
    assert response.json()["final_score"] == pytest.approx(83.8)
    assert response.json()["risk_band"] == "Low Risk"
    assert len(client.saved) == 1  # the assessment was logged


def test_signed_in_user_can_read_history(client):
    token = sign_in(client)
    assert client.get("/history", headers=bearer(token)).status_code == 200


def test_garbage_token_is_rejected(client):
    response = client.get("/history", headers=bearer("not-a-real-token"))
    assert response.status_code == 401


def test_expired_token_is_rejected(client):
    expired = jwt.encode({"sub": "analyst", "exp": int(time.time()) - 60}, SECRET, algorithm="HS256")
    response = client.get("/history", headers=bearer(expired))
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


def test_token_signed_with_another_key_is_rejected(client):
    forged = jwt.encode(
        {"sub": "analyst", "exp": int(time.time()) + 3600},
        "a-different-secret-that-an-attacker-would-have-guessed",
        algorithm="HS256",
    )
    assert client.get("/history", headers=bearer(forged)).status_code == 401


def test_validation_still_applies_when_signed_in(client):
    token = sign_in(client)
    bad = dict(VALID_INPUTS, txn_regularity=150)  # scores are capped at 100
    response = client.post("/assess-risk", json=bad, headers=bearer(token))
    assert response.status_code == 422
    assert client.saved == []


def test_server_refuses_to_sign_in_when_not_configured(client, monkeypatch):
    monkeypatch.delenv("JWT_SECRET")
    monkeypatch.delenv("AUTH_PASSWORD")
    response = client.post("/login", json={"username": "analyst", "password": "anything"})
    assert response.status_code == 503
