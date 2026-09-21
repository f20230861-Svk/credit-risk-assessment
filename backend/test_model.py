"""Unit tests for the credit risk scoring model (backend/model.py)."""

import pytest

from model import WEIGHTS, compute_income_score, compute_risk_score


def score(txn, utility, inflow, mobile, social):
    """Shorthand so each test reads as five numbers in a fixed order."""
    return compute_risk_score(
        txn_regularity=txn,
        utility_payment_score=utility,
        avg_monthly_inflow=inflow,
        mobile_usage_stability=mobile,
        social_signal_score=social,
    )


def test_weights_sum_to_one():
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_income_score_scales_and_caps():
    assert compute_income_score(0) == 0
    assert compute_income_score(25000) == 50
    assert compute_income_score(50000) == 100
    assert compute_income_score(200000) == 100  # capped at full points


@pytest.mark.parametrize(
    "inputs, expected_score, expected_band",
    [
        ((85, 90, 42000, 80, 70), 83.8, "Low Risk"),      # steady earner
        ((55, 60, 22000, 60, 50), 54.3, "Medium Risk"),   # seasonal earner
        ((30, 35, 9000, 40, 30), 30.35, "High Risk"),     # irregular earner
    ],
)
def test_example_borrowers(inputs, expected_score, expected_band):
    result = score(*inputs)
    assert result["final_score"] == pytest.approx(expected_score)
    assert result["risk_band"] == expected_band


def test_band_boundaries():
    # 70 and above is Low Risk, 40 and above is Medium Risk.
    assert score(70, 70, 35000, 70, 70)["risk_band"] == "Low Risk"       # exactly 70
    assert score(40, 40, 20000, 40, 40)["risk_band"] == "Medium Risk"    # exactly 40
    assert score(39, 39, 19500, 39, 39)["risk_band"] == "High Risk"      # just below 40


def test_extremes():
    worst = score(0, 0, 0, 0, 0)
    assert worst["final_score"] == 0
    assert worst["risk_band"] == "High Risk"

    best = score(100, 100, 50000, 100, 100)
    assert best["final_score"] == 100
    assert best["risk_band"] == "Low Risk"


def test_breakdown_adds_up_to_final_score():
    result = score(85, 90, 42000, 80, 70)
    assert sum(result["breakdown"].values()) == pytest.approx(
        result["final_score"], abs=0.01
    )


def test_each_signal_is_capped_by_its_weight():
    result = score(100, 100, 50000, 100, 100)
    for key, points in result["breakdown"].items():
        assert points == pytest.approx(WEIGHTS[key] * 100)


def test_more_income_never_lowers_the_score():
    lower = score(60, 60, 10000, 60, 60)["final_score"]
    higher = score(60, 60, 40000, 60, 60)["final_score"]
    assert higher > lower
