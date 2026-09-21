"""Tests for the fairness audit.

The type of area (urban, semi-urban or rural) is stored with every assessment so
that outcomes can be compared across areas. It must never change a score.
"""

import inspect

import pytest
from fastapi.testclient import TestClient

import main
from model import compute_risk_score

BORROWER = {
    "monthly_income": 22000,
    "lowest_month_income": 9000,
    "household_size": 5,
    "household_expenses": 14000,
    "existing_loan_payments": 2000,
    "active_loans": 1,
    "loan_amount": 40000,
    "tenure_months": 12,
    "annual_rate_percent": 24,
    "bills_on_time": 9,
    "failed_payments": 1,
    "avg_balance": 15000,
    "months_in_work": 18,
    "vehicle": "cycle",
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AUTH_USERNAME", "analyst")
    monkeypatch.setenv("AUTH_PASSWORD", "correct-horse-battery")
    monkeypatch.setenv("JWT_SECRET", "test-secret-that-is-long-enough-for-hs256-signing")
    monkeypatch.setattr(main, "generate_explanation", lambda result: None)
    saved = []
    monkeypatch.setattr(main, "log_assessment", lambda inputs, result: saved.append(inputs))
    test_client = TestClient(main.app)
    test_client.saved = saved
    return test_client


def headers(client):
    token = client.post(
        "/login", json={"username": "analyst", "password": "correct-horse-battery"}
    ).json()["access_token"]
    return {"Authorization": "Bearer " + token}


def test_the_scorecard_has_no_way_to_receive_the_area_type():
    assert "area_type" not in inspect.signature(compute_risk_score).parameters


def test_the_area_type_never_changes_the_score(client):
    results = {}
    for area in ("urban", "semi_urban", "rural"):
        body = client.post("/assess-risk", json=dict(BORROWER, area_type=area), headers=headers(client)).json()
        results[area] = (body["final_score"], body["risk_band"], body["breakdown"], body["details"])
    assert results["urban"] == results["semi_urban"] == results["rural"]


def test_the_area_type_is_saved_for_the_audit(client):
    client.post("/assess-risk", json=dict(BORROWER, area_type="rural"), headers=headers(client))
    assert client.saved[0]["area_type"] == "rural"


def test_the_fairness_report_needs_sign_in(client):
    assert client.get("/fairness-report").status_code == 401


def test_the_fairness_report_returns_outcomes_by_area(client, monkeypatch):
    rows = [{"area_type": "rural", "assessments": 4, "average_score": 52.5, "high_risk_percent": 25.0},
            {"area_type": "urban", "assessments": 6, "average_score": 58.1, "high_risk_percent": 17.0}]
    monkeypatch.setattr(main, "get_fairness_report", lambda: rows)
    response = client.get("/fairness-report", headers=headers(client))
    assert response.status_code == 200
    assert response.json() == rows
