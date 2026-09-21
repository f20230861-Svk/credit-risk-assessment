"""
Credit risk scorecard for borrowers without a credit file.

Nine facts about the borrower are turned into eight factor scores (0 to 100).
The factor scores are weighted into one score out of 100, which maps to a band:
Low, Medium or High Risk. Two policy rules can force the band to High Risk
whatever the score. Every number is hand-set for this prototype and would be
trained on real repayment data in production.

The eight factors answer three questions a lender asks:
  Can they afford it?     debt burden, income stability, income level
  Will they pay?          bills paid on time, failed payments
  What if something goes wrong?  savings cushion, assets, time in work
"""

WEIGHTS = {
    "debt_burden": 0.20,
    "income_stability": 0.20,
    "bills_on_time": 0.20,
    "failed_payments": 0.10,
    "savings_cushion": 0.10,
    "income_level": 0.10,
    "assets": 0.05,
    "time_in_work": 0.05,
}

# Hand-set thresholds
DEBT_FULL_POINTS_AT = 0.30      # loan payments at or below 30% of income: full points
DEBT_ZERO_POINTS_AT = 0.60      # loan payments at or above 60% of income: no points
INCOME_FOR_FULL_POINTS = 50000  # rupees a month
BILLS_WINDOW = 12               # bills looked at
CUSHION_MONTHS_FOR_FULL = 3     # months of income held as savings
MONTHS_IN_WORK_FOR_FULL = 24

FAILED_PAYMENT_SCORES = {0: 100, 1: 60, 2: 30}  # 3 or more: 0

VEHICLE_SCORES = {
    "none": 0,
    "cycle": 25,
    "two_wheeler": 60,
    "second_hand_car": 80,
    "car": 100,
}

VEHICLE_LABELS = {
    "none": "No vehicle",
    "cycle": "Owns a cycle",
    "two_wheeler": "Owns a two-wheeler",
    "second_hand_car": "Owns a second-hand car",
    "car": "Owns a car",
}


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def debt_burden_ratio(monthly_income, existing_emi, requested_emi):
    """Loan payments (existing plus new) as a share of income, or None with no income."""
    if monthly_income <= 0:
        return None
    return (existing_emi + requested_emi) / monthly_income


def score_debt_burden(ratio):
    if ratio is None:
        return 0.0
    span = DEBT_ZERO_POINTS_AT - DEBT_FULL_POINTS_AT
    return round(clamp((DEBT_ZERO_POINTS_AT - ratio) / span) * 100, 2)


def income_stability_share(monthly_income, lowest_month_income):
    """The lowest month as a share of the average month, or None with no income."""
    if monthly_income <= 0:
        return None
    return clamp(lowest_month_income / monthly_income)


def score_income_stability(share):
    return 0.0 if share is None else round(share * 100, 2)


def score_bills_on_time(bills_on_time):
    return round(clamp(int(bills_on_time) / BILLS_WINDOW) * 100, 2)


def score_failed_payments(failed_payments):
    return float(FAILED_PAYMENT_SCORES.get(int(failed_payments), 0))


def cushion_in_months(avg_balance, monthly_income):
    return 0.0 if monthly_income <= 0 else avg_balance / monthly_income


def score_savings_cushion(months):
    return round(clamp(months / CUSHION_MONTHS_FOR_FULL) * 100, 2)


def score_income_level(monthly_income):
    return round(clamp(monthly_income / INCOME_FOR_FULL_POINTS) * 100, 2)


def score_assets(vehicle):
    return float(VEHICLE_SCORES[vehicle])


def score_time_in_work(months_in_work):
    return round(clamp(months_in_work / MONTHS_IN_WORK_FOR_FULL) * 100, 2)


def band_for_score(score):
    if score >= 70:
        return "Low Risk"
    if score >= 40:
        return "Medium Risk"
    return "High Risk"


def plural(count, word):
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def compute_risk_score(
    monthly_income,
    lowest_month_income,
    existing_emi,
    requested_emi,
    bills_on_time,
    failed_payments,
    avg_balance,
    vehicle,
    months_in_work,
) -> dict:
    burden = debt_burden_ratio(monthly_income, existing_emi, requested_emi)
    stability = income_stability_share(monthly_income, lowest_month_income)
    months_cushion = cushion_in_months(avg_balance, monthly_income)

    factor_scores = {
        "debt_burden": score_debt_burden(burden),
        "income_stability": score_income_stability(stability),
        "bills_on_time": score_bills_on_time(bills_on_time),
        "failed_payments": score_failed_payments(failed_payments),
        "savings_cushion": score_savings_cushion(months_cushion),
        "income_level": score_income_level(monthly_income),
        "assets": score_assets(vehicle),
        "time_in_work": score_time_in_work(months_in_work),
    }

    contributions = {key: factor_scores[key] * WEIGHTS[key] for key in WEIGHTS}
    final_score = round(sum(contributions.values()), 2)
    risk_band = band_for_score(final_score)

    # Policy rules: a lender would not lend in these cases whatever else is true.
    overrides = []
    if monthly_income <= 0:
        overrides.append("No income in the last 6 months")
    elif burden is not None and burden >= 1.0:
        overrides.append("Loan payments would use up all of the income")
    if overrides:
        risk_band = "High Risk"

    details = {
        "debt_burden": (
            "No income to measure loan payments against"
            if burden is None
            else f"Loan payments would use {burden * 100:.0f}% of income"
        ),
        "income_stability": (
            "No income to measure"
            if stability is None
            else f"Lowest month is {stability * 100:.0f}% of the average month"
        ),
        "bills_on_time": f"{int(bills_on_time)} of {BILLS_WINDOW} bills paid on time",
        "failed_payments": f"{plural(int(failed_payments), 'failed payment')} in the last 6 months",
        "savings_cushion": f"Average balance covers {months_cushion:.1f} months of income",
        "income_level": f"Average income Rs {monthly_income:,.0f} a month",
        "assets": VEHICLE_LABELS[vehicle],
        "time_in_work": f"{plural(int(months_in_work), 'month')} in current work",
    }

    return {
        "final_score": final_score,
        "risk_band": risk_band,
        "breakdown": contributions,
        "details": details,
        "overrides": overrides,
    }
