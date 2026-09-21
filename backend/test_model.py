"""Unit tests for the credit risk scorecard (backend/model.py)."""

import pytest

from model import (
    WEIGHTS,
    band_for_score,
    cushion_in_months,
    debt_burden_ratio,
    compute_risk_score,
    score_assets,
    score_bills_on_time,
    score_debt_burden,
    score_failed_payments,
    score_income_level,
    score_income_stability,
    score_savings_cushion,
    score_time_in_work,
    income_stability_share,
)

STEADY = dict(monthly_income=42000, lowest_month_income=38000, existing_emi=3000, requested_emi=4000,
              bills_on_time=12, failed_payments=0, avg_balance=60000, vehicle="two_wheeler", months_in_work=36)
SEASONAL = dict(monthly_income=22000, lowest_month_income=9000, existing_emi=2000, requested_emi=4000,
                bills_on_time=9, failed_payments=1, avg_balance=15000, vehicle="cycle", months_in_work=18)
IRREGULAR = dict(monthly_income=12000, lowest_month_income=3000, existing_emi=3000, requested_emi=5000,
                 bills_on_time=4, failed_payments=3, avg_balance=2000, vehicle="none", months_in_work=5)
NO_INCOME = dict(monthly_income=0, lowest_month_income=0, existing_emi=0, requested_emi=5000,
                 bills_on_time=12, failed_payments=0, avg_balance=20000, vehicle="car", months_in_work=30)
BEST = dict(monthly_income=50000, lowest_month_income=50000, existing_emi=0, requested_emi=5000,
            bills_on_time=12, failed_payments=0, avg_balance=150000, vehicle="car", months_in_work=24)
WORST = dict(monthly_income=1000, lowest_month_income=0, existing_emi=900, requested_emi=500,
             bills_on_time=0, failed_payments=5, avg_balance=0, vehicle="none", months_in_work=0)


def test_weights_sum_to_one():
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_the_three_questions_a_lender_asks_all_carry_weight():
    afford = WEIGHTS["debt_burden"] + WEIGHTS["income_stability"] + WEIGHTS["income_level"]
    will_pay = WEIGHTS["bills_on_time"] + WEIGHTS["failed_payments"]
    cushion = WEIGHTS["savings_cushion"] + WEIGHTS["assets"] + WEIGHTS["time_in_work"]
    assert (afford, will_pay, cushion) == pytest.approx((0.50, 0.30, 0.20))


# ---------- each factor on its own ----------

@pytest.mark.parametrize("ratio, expected", [
    (None, 0),      # no income to measure against
    (0.0, 100),
    (0.30, 100),    # at or below 30% of income: full points
    (0.45, 50),     # halfway between 30% and 60%
    (0.60, 0),      # at or above 60%: no points
    (0.90, 0),
])
def test_debt_burden_score(ratio, expected):
    assert score_debt_burden(ratio) == pytest.approx(expected)


def test_debt_burden_ratio_counts_existing_and_new_installments():
    assert debt_burden_ratio(40000, 6000, 4000) == pytest.approx(0.25)
    assert debt_burden_ratio(0, 0, 4000) is None


@pytest.mark.parametrize("income, lowest, expected", [
    (30000, 30000, 100),   # income never dips
    (30000, 15000, 50),    # lowest month is half the average
    (30000, 0, 0),
    (0, 0, 0),             # no income
])
def test_income_stability_score(income, lowest, expected):
    assert score_income_stability(income_stability_share(income, lowest)) == pytest.approx(expected)


@pytest.mark.parametrize("paid, expected", [(12, 100), (9, 75), (6, 50), (0, 0)])
def test_bills_on_time_score(paid, expected):
    assert score_bills_on_time(paid) == pytest.approx(expected)


@pytest.mark.parametrize("failed, expected", [(0, 100), (1, 60), (2, 30), (3, 0), (10, 0)])
def test_failed_payments_score(failed, expected):
    assert score_failed_payments(failed) == expected


@pytest.mark.parametrize("balance, income, expected", [
    (90000, 30000, 100),   # three months of income held: full points
    (45000, 30000, 50),    # one and a half months
    (300000, 30000, 100),  # more than three months earns no extra
    (5000, 0, 0),          # no income
])
def test_savings_cushion_score(balance, income, expected):
    assert score_savings_cushion(cushion_in_months(balance, income)) == pytest.approx(expected)


@pytest.mark.parametrize("income, expected", [(0, 0), (25000, 50), (50000, 100), (200000, 100)])
def test_income_level_score(income, expected):
    assert score_income_level(income) == pytest.approx(expected)


@pytest.mark.parametrize("vehicle, expected", [
    ("none", 0), ("cycle", 25), ("two_wheeler", 60), ("second_hand_car", 80), ("car", 100),
])
def test_assets_score(vehicle, expected):
    assert score_assets(vehicle) == expected


@pytest.mark.parametrize("months, expected", [(0, 0), (12, 50), (24, 100), (120, 100)])
def test_time_in_work_score(months, expected):
    assert score_time_in_work(months) == pytest.approx(expected)


# ---------- the whole scorecard ----------

@pytest.mark.parametrize("inputs, expected_score, expected_band", [
    (STEADY, 89.26, "Low Risk"),
    (SEASONAL, 60.86, "Medium Risk"),
    (IRREGULAR, 15.66, "High Risk"),
])
def test_example_borrowers(inputs, expected_score, expected_band):
    result = compute_risk_score(**inputs)
    assert result["final_score"] == pytest.approx(expected_score)
    assert result["risk_band"] == expected_band
    assert result["overrides"] == []


@pytest.mark.parametrize("score, band", [
    (100, "Low Risk"), (70, "Low Risk"), (69.99, "Medium Risk"),
    (40, "Medium Risk"), (39.99, "High Risk"), (0, "High Risk"),
])
def test_band_boundaries(score, band):
    assert band_for_score(score) == band


def test_extremes():
    best = compute_risk_score(**BEST)
    worst = compute_risk_score(**WORST)
    assert best["final_score"] == pytest.approx(100)
    assert best["risk_band"] == "Low Risk"
    assert worst["final_score"] == pytest.approx(0.2)   # even Rs 1,000 of income earns 0.2 points
    assert worst["risk_band"] == "High Risk"


def test_breakdown_adds_up_to_final_score_and_respects_each_maximum():
    result = compute_risk_score(**STEADY)
    assert sum(result["breakdown"].values()) == pytest.approx(result["final_score"], abs=0.01)
    best = compute_risk_score(**BEST)
    for key, points in best["breakdown"].items():
        assert points == pytest.approx(WEIGHTS[key] * 100)


def test_every_factor_has_a_plain_language_detail():
    result = compute_risk_score(**STEADY)
    assert set(result["details"]) == set(WEIGHTS)
    assert result["details"]["debt_burden"] == "Loan payments would use 17% of income"
    assert result["details"]["bills_on_time"] == "12 of 12 bills paid on time"
    assert result["details"]["assets"] == "Owns a two-wheeler"


# ---------- policy rules ----------

def test_no_income_forces_high_risk_even_with_a_clean_record():
    result = compute_risk_score(**NO_INCOME)
    assert result["final_score"] == pytest.approx(40)   # the record earns 40 points
    assert result["risk_band"] == "High Risk"           # but a rule overrides the band
    assert result["overrides"] == ["No income in the last 6 months"]


def test_loan_payments_that_use_up_all_income_force_high_risk():
    strong_record = dict(BEST, monthly_income=20000, lowest_month_income=20000,
                         existing_emi=10000, requested_emi=12000)
    result = compute_risk_score(**strong_record)
    assert result["risk_band"] == "High Risk"
    assert result["overrides"] == ["Loan payments would use up all of the income"]


def test_no_rule_applies_to_a_normal_borrower():
    assert compute_risk_score(**STEADY)["overrides"] == []


# ---------- how the score should move ----------

def test_more_bills_paid_on_time_never_lowers_the_score():
    low = compute_risk_score(**dict(SEASONAL, bills_on_time=6))["final_score"]
    high = compute_risk_score(**dict(SEASONAL, bills_on_time=12))["final_score"]
    assert high > low


def test_a_bigger_new_installment_never_raises_the_score():
    small = compute_risk_score(**dict(SEASONAL, requested_emi=2000))["final_score"]
    large = compute_risk_score(**dict(SEASONAL, requested_emi=9000))["final_score"]
    assert large <= small


def test_a_failed_payment_costs_points():
    clean = compute_risk_score(**dict(STEADY, failed_payments=0))["final_score"]
    one_bounce = compute_risk_score(**dict(STEADY, failed_payments=1))["final_score"]
    assert clean - one_bounce == pytest.approx(4.0)   # 100 - 60 = 40 points, at a 10% weight


def test_owning_a_better_vehicle_helps_a_little_and_only_a_little():
    none = compute_risk_score(**dict(STEADY, vehicle="none"))["final_score"]
    car = compute_risk_score(**dict(STEADY, vehicle="car"))["final_score"]
    assert 0 < car - none <= 5    # assets carry a 5% weight
