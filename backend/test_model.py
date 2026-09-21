"""Unit tests for the credit risk scorecard (backend/model.py)."""

import pytest

from model import (
    WEIGHTS,
    band_for_score,
    calculate_emi,
    compute_risk_score,
    cushion_in_months,
    essential_costs,
    income_stability_share,
    loan_burden_ratio,
    score_active_loans,
    score_assets,
    score_bills_on_time,
    score_disposable_income,
    score_failed_payments,
    score_income_per_person,
    score_income_stability,
    score_loan_burden,
    score_savings_cushion,
    score_time_in_work,
)

STEADY = dict(monthly_income=42000, lowest_month_income=38000, household_size=4, household_expenses=20000,
              existing_loan_payments=3000, active_loans=1, loan_amount=60000, tenure_months=12,
              annual_rate_percent=24, bills_on_time=12, failed_payments=0, avg_balance=60000,
              months_in_work=36, vehicle="two_wheeler")
SEASONAL = dict(monthly_income=22000, lowest_month_income=9000, household_size=5, household_expenses=14000,
                existing_loan_payments=2000, active_loans=1, loan_amount=40000, tenure_months=12,
                annual_rate_percent=24, bills_on_time=9, failed_payments=1, avg_balance=15000,
                months_in_work=18, vehicle="cycle")
IRREGULAR = dict(monthly_income=12000, lowest_month_income=3000, household_size=3, household_expenses=8000,
                 existing_loan_payments=1000, active_loans=1, loan_amount=20000, tenure_months=12,
                 annual_rate_percent=24, bills_on_time=4, failed_payments=3, avg_balance=2000,
                 months_in_work=5, vehicle="none")
NO_INCOME = dict(monthly_income=0, lowest_month_income=0, household_size=4, household_expenses=12000,
                 existing_loan_payments=0, active_loans=0, loan_amount=30000, tenure_months=12,
                 annual_rate_percent=24, bills_on_time=12, failed_payments=0, avg_balance=20000,
                 months_in_work=30, vehicle="car")
BEST = dict(monthly_income=60000, lowest_month_income=60000, household_size=4, household_expenses=15000,
            existing_loan_payments=0, active_loans=0, loan_amount=50000, tenure_months=12,
            annual_rate_percent=24, bills_on_time=12, failed_payments=0, avg_balance=180000,
            months_in_work=24, vehicle="car")
WORST = dict(monthly_income=1000, lowest_month_income=0, household_size=6, household_expenses=0,
             existing_loan_payments=900, active_loans=5, loan_amount=6000, tenure_months=12,
             annual_rate_percent=24, bills_on_time=0, failed_payments=5, avg_balance=0,
             months_in_work=0, vehicle="none")


def test_weights_sum_to_one():
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_the_three_questions_a_lender_asks_all_carry_weight():
    afford = sum(WEIGHTS[k] for k in ("loan_burden", "disposable_income", "income_stability", "income_per_person"))
    will_pay = sum(WEIGHTS[k] for k in ("bills_on_time", "failed_payments", "active_loans"))
    cushion = sum(WEIGHTS[k] for k in ("savings_cushion", "time_in_work", "assets"))
    assert (afford, will_pay, cushion) == pytest.approx((0.50, 0.30, 0.20))


# ---------- each factor on its own ----------

@pytest.mark.parametrize("ratio, expected", [
    (None, 0),      # no income to measure against
    (0.0, 100),
    (0.30, 100),    # at or below 30% of income: full points
    (0.40, 50),     # halfway between 30% and 50%
    (0.50, 0),      # at the limit: no points
    (0.90, 0),
])
def test_loan_burden_score(ratio, expected):
    assert score_loan_burden(ratio) == pytest.approx(expected)


def test_loan_burden_counts_existing_payments_and_the_new_installment():
    assert loan_burden_ratio(40000, 6000, 4000) == pytest.approx(0.25)
    assert loan_burden_ratio(0, 0, 4000) is None


@pytest.mark.parametrize("amount, rate, months, expected", [
    (100000, 12, 12, 8884.88),   # the standard textbook example
    (120000, 0, 12, 10000.0),    # no interest: the amount split evenly
    (0, 24, 12, 0.0),            # no loan, no installment
])
def test_emi_uses_the_standard_formula(amount, rate, months, expected):
    assert calculate_emi(amount, rate, months) == pytest.approx(expected, abs=0.01)


def test_a_longer_tenure_lowers_the_installment_and_a_higher_rate_raises_it():
    assert calculate_emi(60000, 24, 24) < calculate_emi(60000, 24, 12)
    assert calculate_emi(60000, 30, 12) > calculate_emi(60000, 24, 12)


def test_essentials_are_raised_to_a_minimum_per_person():
    assert essential_costs(20000, 4) == (20000, False)     # declared is above 4 x 3,000
    assert essential_costs(5000, 4) == (12000, True)       # understated, so the floor applies


@pytest.mark.parametrize("residual, income, expected", [
    (10000, 40000, 100),    # 25% of income left: full points
    (8000, 40000, 100),     # exactly 20%
    (4000, 40000, 50),      # 10% left
    (0, 40000, 0),
    (-5000, 40000, 0),      # short of essentials: no points
    (1000, 0, 0),           # no income
])
def test_disposable_income_score(residual, income, expected):
    assert score_disposable_income(residual, income) == pytest.approx(expected)


@pytest.mark.parametrize("income, lowest, expected", [
    (30000, 30000, 100),   # income never dips
    (30000, 15000, 50),    # lowest month is half the average
    (30000, 0, 0),
    (0, 0, 0),             # no income
])
def test_income_stability_score(income, lowest, expected):
    assert score_income_stability(income_stability_share(income, lowest)) == pytest.approx(expected)


@pytest.mark.parametrize("income, size, expected", [
    (50000, 4, 100),      # Rs 12,500 a person: full points
    (25000, 4, 50),
    (25000, 1, 100),      # the same income for one person is plenty
    (0, 3, 0),
])
def test_income_per_person_score(income, size, expected):
    assert score_income_per_person(income, size) == pytest.approx(expected)


@pytest.mark.parametrize("paid, expected", [(12, 100), (9, 75), (6, 50), (0, 0)])
def test_bills_on_time_score(paid, expected):
    assert score_bills_on_time(paid) == pytest.approx(expected)


@pytest.mark.parametrize("failed, expected", [(0, 100), (1, 60), (2, 30), (3, 0), (10, 0)])
def test_failed_payments_score(failed, expected):
    assert score_failed_payments(failed) == expected


@pytest.mark.parametrize("loans, expected", [(0, 100), (1, 85), (2, 60), (3, 30), (4, 0), (9, 0)])
def test_active_loans_score(loans, expected):
    assert score_active_loans(loans) == expected


@pytest.mark.parametrize("balance, income, expected", [
    (90000, 30000, 100),   # three months of income held: full points
    (45000, 30000, 50),    # one and a half months
    (300000, 30000, 100),  # more than three months earns no extra
    (5000, 0, 0),          # no income
])
def test_savings_cushion_score(balance, income, expected):
    assert score_savings_cushion(cushion_in_months(balance, income)) == pytest.approx(expected)


@pytest.mark.parametrize("months, expected", [(0, 0), (12, 50), (24, 100), (120, 100)])
def test_time_in_work_score(months, expected):
    assert score_time_in_work(months) == pytest.approx(expected)


@pytest.mark.parametrize("vehicle, expected", [
    ("none", 0), ("cycle", 25), ("two_wheeler", 60), ("second_hand_car", 80), ("car", 100),
])
def test_assets_score(vehicle, expected):
    assert score_assets(vehicle) == expected


# ---------- the whole scorecard ----------

@pytest.mark.parametrize("inputs, expected_score, expected_band", [
    (STEADY, 89.48, "Low Risk"),
    (SEASONAL, 56.32, "Medium Risk"),
    (IRREGULAR, 33.58, "High Risk"),
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
    assert worst["final_score"] < 1
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
    assert result["details"]["loan_burden"] == (
        "Existing loan payments Rs 3,000 plus the new installment Rs 5,674 is 21% of income")
    assert result["details"]["bills_on_time"] == "12 of 12 bills paid on time"
    assert result["details"]["active_loans"] == "1 loan being repaid"
    assert result["details"]["assets"] == "Owns a two-wheeler"


def test_the_result_shows_the_installment_and_what_is_left_over():
    result = compute_risk_score(**STEADY)
    assert result["loan_emi"] == pytest.approx(5673.58)
    assert result["residual_income"] == pytest.approx(13326.42, abs=0.01)


def test_understated_expenses_are_replaced_by_the_minimum_and_the_page_says_so():
    result = compute_risk_score(**dict(STEADY, household_expenses=2000))
    # 4 people x Rs 3,000 = Rs 12,000 is used instead of Rs 2,000
    assert result["residual_income"] == pytest.approx(42000 - 3000 - 5673.58 - 12000, abs=0.01)
    assert "essentials raised to the minimum" in result["details"]["disposable_income"]


# ---------- policy rules ----------

def test_no_income_forces_high_risk_even_with_a_clean_record():
    result = compute_risk_score(**NO_INCOME)
    assert result["final_score"] == pytest.approx(40)   # the record earns 40 points
    assert result["risk_band"] == "High Risk"           # but a rule overrides the band
    assert result["overrides"] == ["No income in the last 6 months"]


def test_loan_payments_above_50_percent_of_income_force_high_risk():
    # the RBI limit on loan repayments for low-income households
    result = compute_risk_score(**dict(STEADY, loan_amount=300000))
    assert result["risk_band"] == "High Risk"
    assert "Loan payments would use more than 50% of income" in result["overrides"]


def test_income_that_cannot_cover_essentials_and_the_loan_forces_high_risk():
    # loan payments are only 25% of income, but essentials are large
    result = compute_risk_score(**dict(STEADY, household_expenses=35000))
    assert result["residual_income"] < 0
    assert result["risk_band"] == "High Risk"
    assert result["overrides"] == ["Income would not cover essential costs and loan payments"]


def test_exactly_50_percent_is_still_allowed():
    # income 20,000; existing 4,000; a loan whose installment is exactly 6,000 (no interest, 12 months)
    result = compute_risk_score(**dict(STEADY, monthly_income=20000, lowest_month_income=20000,
                                       household_expenses=8000, household_size=2, existing_loan_payments=4000,
                                       loan_amount=72000, annual_rate_percent=0, tenure_months=12))
    assert result["loan_emi"] == pytest.approx(6000)
    assert "Loan payments would use more than 50% of income" not in result["overrides"]


def test_the_same_borrower_can_be_fine_for_a_small_loan_and_refused_for_a_large_one():
    small = compute_risk_score(**dict(STEADY, loan_amount=30000))
    large = compute_risk_score(**dict(STEADY, loan_amount=300000))
    assert small["risk_band"] == "Low Risk"
    assert large["risk_band"] == "High Risk"


def test_no_rule_applies_to_a_normal_borrower():
    assert compute_risk_score(**STEADY)["overrides"] == []


# ---------- how the score should move ----------

def test_more_bills_paid_on_time_never_lowers_the_score():
    low = compute_risk_score(**dict(SEASONAL, bills_on_time=6))["final_score"]
    high = compute_risk_score(**dict(SEASONAL, bills_on_time=12))["final_score"]
    assert high > low


def test_a_bigger_loan_never_raises_the_score():
    small = compute_risk_score(**dict(SEASONAL, loan_amount=20000))["final_score"]
    large = compute_risk_score(**dict(SEASONAL, loan_amount=90000))["final_score"]
    assert large <= small


def test_more_active_loans_never_raise_the_score():
    one = compute_risk_score(**dict(STEADY, active_loans=1))["final_score"]
    four = compute_risk_score(**dict(STEADY, active_loans=4))["final_score"]
    assert four < one


def test_a_failed_payment_costs_points():
    clean = compute_risk_score(**dict(STEADY, failed_payments=0))["final_score"]
    one_bounce = compute_risk_score(**dict(STEADY, failed_payments=1))["final_score"]
    assert clean - one_bounce == pytest.approx(3.2)   # 100 - 60 = 40 points, at an 8% weight


def test_owning_a_better_vehicle_helps_a_little_and_only_a_little():
    none = compute_risk_score(**dict(STEADY, vehicle="none"))["final_score"]
    car = compute_risk_score(**dict(STEADY, vehicle="car"))["final_score"]
    assert 0 < car - none <= 5    # assets carry a 5% weight


def test_a_bigger_household_on_the_same_income_is_no_better_off():
    small = compute_risk_score(**dict(SEASONAL, household_size=2))["final_score"]
    large = compute_risk_score(**dict(SEASONAL, household_size=6))["final_score"]
    assert large <= small
