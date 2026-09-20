"""
Credit risk scoring model using alternative data signals.
"""

WEIGHTS = {
    "txn_regularity": 0.30,
    "utility_payment_score": 0.25,
    "income_score": 0.20,
    "mobile_usage_stability": 0.15,
    "social_signal_score": 0.10,
}


def compute_income_score(avg_monthly_inflow: float) -> float:
    capped = min(avg_monthly_inflow / 50000, 1.0)
    return round(capped * 100, 2)


def compute_risk_score(
    txn_regularity: float,
    utility_payment_score: float,
    avg_monthly_inflow: float,
    mobile_usage_stability: float,
    social_signal_score: float,
) -> dict:
    income_score = compute_income_score(avg_monthly_inflow)

    contributions = {
        "txn_regularity": txn_regularity * WEIGHTS["txn_regularity"],
        "utility_payment_score": utility_payment_score * WEIGHTS["utility_payment_score"],
        "income_score": income_score * WEIGHTS["income_score"],
        "mobile_usage_stability": mobile_usage_stability * WEIGHTS["mobile_usage_stability"],
        "social_signal_score": social_signal_score * WEIGHTS["social_signal_score"],
    }

    final_score = round(sum(contributions.values()), 2)

    if final_score >= 70:
        risk_band = "Low Risk"
    elif final_score >= 40:
        risk_band = "Medium Risk"
    else:
        risk_band = "High Risk"

    return {
        "final_score": final_score,
        "risk_band": risk_band,
        "breakdown": contributions,
        "income_score": income_score,
    }
