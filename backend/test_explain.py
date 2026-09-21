"""Tests for the optional AI explanation (backend/explain.py).

No test calls the real AI service or the real database.
"""

import pytest
import requests
from fastapi.testclient import TestClient

import explain
import main
from model import compute_risk_score

STEADY = dict(monthly_income=42000, lowest_month_income=38000, household_size=4, household_expenses=20000,
              existing_loan_payments=3000, active_loans=1, loan_amount=60000, tenure_months=12,
              annual_rate_percent=24, bills_on_time=12, failed_payments=0, avg_balance=60000,
              months_in_work=36, vehicle="two_wheeler")
SEASONAL = dict(monthly_income=22000, lowest_month_income=9000, household_size=5, household_expenses=14000,
                existing_loan_payments=2000, active_loans=1, loan_amount=40000, tenure_months=12,
                annual_rate_percent=24, bills_on_time=9, failed_payments=1, avg_balance=15000,
                months_in_work=18, vehicle="cycle")
NO_INCOME = dict(monthly_income=0, lowest_month_income=0, household_size=4, household_expenses=12000,
                 existing_loan_payments=0, active_loans=0, loan_amount=30000, tenure_months=12,
                 annual_rate_percent=24, bills_on_time=12, failed_payments=0, avg_balance=20000,
                 months_in_work=30, vehicle="car")
# what the API receives: the same facts plus the audit-only area type
API_STEADY = dict(STEADY, area_type="urban")
API_NO_INCOME = dict(NO_INCOME, area_type="rural")


def scored(inputs):
    return compute_risk_score(**inputs)


class FakeResponse:
    def __init__(self, payload=None, status=200):
        self.payload = payload
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(str(self.status))

    def json(self):
        return self.payload


def gemini_reply(text):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


@pytest.fixture
def with_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)


def test_without_a_key_the_feature_is_off_and_makes_no_request(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    def fail(*args, **kwargs):
        raise AssertionError("no request should be made without a key")

    monkeypatch.setattr(explain.requests, "post", fail)
    assert explain.generate_explanation(scored(STEADY)) is None


def test_returns_the_text_from_the_ai(with_key, monkeypatch):
    monkeypatch.setattr(
        explain.requests, "post",
        lambda *a, **k: FakeResponse(gemini_reply("  Bills paid\n on time helped most.  ")),
    )
    assert explain.generate_explanation(scored(STEADY)) == "Bills paid on time helped most."


def test_key_goes_in_a_header_never_in_the_url(with_key, monkeypatch):
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.update(url=url, headers=headers, timeout=timeout)
        return FakeResponse(gemini_reply("ok"))

    monkeypatch.setattr(explain.requests, "post", fake_post)
    explain.generate_explanation(scored(STEADY))

    assert "test-key-123" not in seen["url"]
    assert seen["headers"]["x-goog-api-key"] == "test-key-123"
    assert seen["timeout"] == explain.TIMEOUT_SECONDS


def test_model_can_be_changed_with_a_setting(with_key, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "some-other-model")
    seen = {}

    def fake_post(url, **kwargs):
        seen["url"] = url
        return FakeResponse(gemini_reply("ok"))

    monkeypatch.setattr(explain.requests, "post", fake_post)
    explain.generate_explanation(scored(STEADY))
    assert "some-other-model" in seen["url"]


@pytest.mark.parametrize("status", [429, 500])
def test_http_errors_fall_back_to_none(with_key, monkeypatch, status):
    monkeypatch.setattr(explain.requests, "post", lambda *a, **k: FakeResponse({}, status))
    assert explain.generate_explanation(scored(STEADY)) is None


def test_timeout_falls_back_to_none(with_key, monkeypatch):
    def slow(*args, **kwargs):
        raise requests.Timeout()

    monkeypatch.setattr(explain.requests, "post", slow)
    assert explain.generate_explanation(scored(STEADY)) is None


@pytest.mark.parametrize("payload", [{}, {"candidates": []}, {"candidates": [{}]}, gemini_reply("   ")])
def test_unusable_replies_fall_back_to_none(with_key, monkeypatch, payload):
    monkeypatch.setattr(explain.requests, "post", lambda *a, **k: FakeResponse(payload))
    assert explain.generate_explanation(scored(STEADY)) is None


def test_long_replies_are_cut_at_a_sentence_end(with_key, monkeypatch):
    long_text = "This is a sentence. " * 100
    monkeypatch.setattr(explain.requests, "post", lambda *a, **k: FakeResponse(gemini_reply(long_text)))
    text = explain.generate_explanation(scored(STEADY))
    assert len(text) <= explain.MAX_CHARS
    assert text.endswith(".")


def test_prompt_carries_the_score_and_the_numbers_behind_it():
    prompt = explain.build_prompt(scored(STEADY))
    assert "89.48 out of 100 (Low Risk)" in prompt
    assert "Loan burden: 15 of 15 points" in prompt
    assert "Income stability: 13.57 of 15 points" in prompt
    assert "Existing loan payments Rs 3,000 plus the new installment Rs 5,674 is 21% of income" in prompt
    assert "Rs 13,326 left a month after essentials and loan payments" in prompt
    assert "12 of 12 bills paid on time" in prompt
    assert "already in the top band, Low Risk (the safest band)" in prompt


def test_prompt_names_the_strongest_factor_and_the_biggest_shortfall():
    prompt = explain.build_prompt(scored(SEASONAL))
    # Loan burden earned its full points, the first factor at 100%.
    assert "Strongest factor (highest share of its maximum): Loan burden, 15 of 15 points (100%)" in prompt
    # Disposable income is furthest from its maximum in points (10.85).
    assert "Biggest shortfall (most points still available): Disposable income, 10.85 points" in prompt


def test_prompt_states_how_far_the_next_band_is():
    prompt = explain.build_prompt(scored(SEASONAL))
    assert "56.32 out of 100 (Medium Risk)" in prompt
    assert "Points needed to reach Low Risk: 13.68" in prompt


def test_prompt_explains_a_policy_rule_instead_of_a_next_band():
    prompt = explain.build_prompt(scored(NO_INCOME))
    assert "A policy rule applies: No income in the last 6 months" in prompt
    assert "High Risk whatever the score is" in prompt
    assert "Points needed to reach" not in prompt


def test_prompt_tells_the_ai_not_to_change_the_score_or_decide_the_loan():
    prompt = explain.build_prompt(scored(STEADY))
    assert "Do not change, question or recompute it" in prompt
    assert "do not recommend approving or rejecting" in prompt
    assert "never describe it as high or highest risk" in prompt


def test_prompt_contains_no_personal_details():
    prompt = explain.build_prompt(scored(STEADY)).lower()
    for word in ("full name", "phone number", "address", "aadhaar", "pan card", "email"):
        assert word not in prompt


# ---------- through the API ----------

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AUTH_USERNAME", "analyst")
    monkeypatch.setenv("AUTH_PASSWORD", "correct-horse-battery")
    monkeypatch.setenv("JWT_SECRET", "test-secret-that-is-long-enough-for-hs256-signing")
    monkeypatch.setattr(main, "log_assessment", lambda inputs, result: None)
    return TestClient(main.app)


def signed_in_headers(client):
    token = client.post(
        "/login", json={"username": "analyst", "password": "correct-horse-battery"}
    ).json()["access_token"]
    return {"Authorization": "Bearer " + token}


def test_api_includes_the_ai_explanation_when_available(client, monkeypatch):
    monkeypatch.setattr(main, "generate_explanation", lambda result: "Explained by AI.")
    response = client.post("/assess-risk", json=API_STEADY, headers=signed_in_headers(client))
    body = response.json()
    assert response.status_code == 200
    assert body["ai_explanation"] == "Explained by AI."
    assert body["final_score"] == pytest.approx(89.48)


def test_api_still_scores_when_the_ai_is_unavailable(client, monkeypatch):
    monkeypatch.setattr(main, "generate_explanation", lambda result: None)
    response = client.post("/assess-risk", json=API_STEADY, headers=signed_in_headers(client))
    body = response.json()
    assert response.status_code == 200
    assert body["ai_explanation"] is None
    assert body["final_score"] == pytest.approx(89.48)
    assert body["risk_band"] == "Low Risk"


def test_api_returns_the_details_and_any_policy_rule(client, monkeypatch):
    monkeypatch.setattr(main, "generate_explanation", lambda result: None)
    body = client.post("/assess-risk", json=API_NO_INCOME, headers=signed_in_headers(client)).json()
    assert body["risk_band"] == "High Risk"
    assert body["overrides"] == ["No income in the last 6 months"]
    assert body["details"]["assets"] == "Owns a car"


def test_the_ai_can_never_change_the_score(client, monkeypatch):
    def try_to_meddle(result):
        result["final_score"] = 5  # a misbehaving explainer
        result["breakdown"]["loan_burden"] = 0
        return "text"

    saved = []
    monkeypatch.setattr(main, "log_assessment", lambda inputs, result: saved.append(result["final_score"]))
    monkeypatch.setattr(main, "generate_explanation", try_to_meddle)

    response = client.post("/assess-risk", json=API_STEADY, headers=signed_in_headers(client))
    body = response.json()

    # The explainer only ever sees a copy, so neither the logged score nor the
    # returned score can be altered by it.
    assert saved == [pytest.approx(89.48)]
    assert body["final_score"] == pytest.approx(89.48)
    assert body["breakdown"]["loan_burden"] == pytest.approx(15)
