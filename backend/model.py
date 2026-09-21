"""
Credit risk scorecard for borrowers without a credit file.

Fourteen facts about a household and the loan it asks for are turned into ten
factor scores (0 to 100). The factor scores are weighted into one score out of
100, which maps to a band: Low, Medium or High Risk. Three policy rules can force
the band to High Risk whatever the score. Every number is hand-set for this
prototype and would be fitted on real repayment data in production.

The ten factors answer three questions a lender asks:
  Can they afford it?    loan burden, disposable income, income stability,
                         income per person
  Will they pay?         bills paid on time, failed payments, active loans
  What if something goes wrong?  savings cushion, time in work, assets

A fifteenth fact, the type of area (urban, semi-urban or rural), is never used in
the score. It is stored so that fairness can be audited (see database.py).

The reasoning behind every choice is written down in DESIGN.md.
"""

WEIGHTS = {
    "loan_burden": 0.15,
    "disposable_income": 0.15,
    "income_stability": 0.15,
    "income_per_person": 0.05,
    "bills_on_time": 0.15,
    "failed_payments": 0.08,
    "active_loans": 0.07,
    "savings_cushion": 0.10,
    "time_in_work": 0.05,
    "assets": 0.05,
}

# Hand-set thresholds
LOAN_BURDEN_FULL_AT = 0.30        # loan payments at or below 30% of income: full points
LOAN_BURDEN_LIMIT = 0.50          # above 50% of income: policy rule (the RBI limit for low-income households)
DISPOSABLE_FULL_AT = 0.20         # 20% of income left after essentials and loans: full points
LIVING_COST_FLOOR_PER_PERSON = 3000   # rupees a month, the least essentials are taken to cost per person
INCOME_PER_PERSON_FOR_FULL = 12500    # rupees a month per household member
BILLS_WINDOW = 12                 # bills looked at
CUSHION_MONTHS_FOR_FULL = 3       # months of income held as savings
MONTHS_IN_WORK_FOR_FULL = 24

FAILED_PAYMENT_SCORES = {0: 100, 1: 60, 2: 30}          # 3 or more: 0
ACTIVE_LOAN_SCORES = {0: 100, 1: 85, 2: 60, 3: 30}      # 4 or more: 0

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


def calculate_emi(loan_amount, annual_rate_percent, tenure_months):
    """Monthly installment of a loan, by the standard formula.

    EMI = P * r * (1 + r)^n / ((1 + r)^n - 1), with r the monthly rate.
    """
    if loan_amount <= 0 or tenure_months <= 0:
        return 0.0
    monthly_rate = annual_rate_percent / 12 / 100
    if monthly_rate == 0:
        return loan_amount / tenure_months
    growth = (1 + monthly_rate) ** tenure_months
    return loan_amount * monthly_rate * growth / (growth - 1)


def loan_burden_ratio(monthly_income, existing_loan_payments, new_emi):
    """Loan payments (existing plus new) as a share of household income.

    None when there is no income to measure against.
    """
    if monthly_income <= 0:
        return None
    return (existing_loan_payments + new_emi) / monthly_income


def score_loan_burden(ratio):
    if ratio is None:
        return 0.0
    span = LOAN_BURDEN_LIMIT - LOAN_BURDEN_FULL_AT
    return round(clamp((LOAN_BURDEN_LIMIT - ratio) / span) * 100, 2)


def essential_costs(household_expenses, household_size):
    """Declared essentials, raised to a minimum per person.

    People tend to understate what they spend, so a lender sets a floor.
    Returns (cost used, whether the floor was applied).
    """
    floor = LIVING_COST_FLOOR_PER_PERSON * household_size
    return max(household_expenses, floor), household_expenses < floor


def score_disposable_income(residual, monthly_income):
    if monthly_income <= 0:
        return 0.0
    return round(clamp((residual / monthly_income) / DISPOSABLE_FULL_AT) * 100, 2)


def income_stability_share(monthly_income, lowest_month_income):
    """The lowest month as a share of the average month, or None with no income."""
    if monthly_income <= 0:
        return None
    return clamp(lowest_month_income / monthly_income)


def score_income_stability(share):
    return 0.0 if share is None else round(share * 100, 2)


def score_income_per_person(monthly_income, household_size):
    return round(clamp((monthly_income / household_size) / INCOME_PER_PERSON_FOR_FULL) * 100, 2)


def score_bills_on_time(bills_on_time):
    return round(clamp(int(bills_on_time) / BILLS_WINDOW) * 100, 2)


def score_failed_payments(failed_payments):
    return float(FAILED_PAYMENT_SCORES.get(int(failed_payments), 0))


def score_active_loans(active_loans):
    return float(ACTIVE_LOAN_SCORES.get(int(active_loans), 0))


def cushion_in_months(avg_balance, monthly_income):
    return 0.0 if monthly_income <= 0 else avg_balance / monthly_income


def score_savings_cushion(months):
    return round(clamp(months / CUSHION_MONTHS_FOR_FULL) * 100, 2)


def score_time_in_work(months_in_work):
    return round(clamp(months_in_work / MONTHS_IN_WORK_FOR_FULL) * 100, 2)


def score_assets(vehicle):
    return float(VEHICLE_SCORES[vehicle])


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
    household_size,
    household_expenses,
    existing_loan_payments,
    active_loans,
    loan_amount,
    tenure_months,
    annual_rate_percent,
    bills_on_time,
    failed_payments,
    avg_balance,
    months_in_work,
    vehicle,
) -> dict:
    new_emi = calculate_emi(loan_amount, annual_rate_percent, tenure_months)
    burden = loan_burden_ratio(monthly_income, existing_loan_payments, new_emi)
    stability = income_stability_share(monthly_income, lowest_month_income)
    months_cushion = cushion_in_months(avg_balance, monthly_income)
    essentials, floor_applied = essential_costs(household_expenses, household_size)
    residual = monthly_income - existing_loan_payments - new_emi - essentials
    per_person = monthly_income / household_size

    factor_scores = {
        "loan_burden": score_loan_burden(burden),
        "disposable_income": score_disposable_income(residual, monthly_income),
        "income_stability": score_income_stability(stability),
        "income_per_person": score_income_per_person(monthly_income, household_size),
        "bills_on_time": score_bills_on_time(bills_on_time),
        "failed_payments": score_failed_payments(failed_payments),
        "active_loans": score_active_loans(active_loans),
        "savings_cushion": score_savings_cushion(months_cushion),
        "time_in_work": score_time_in_work(months_in_work),
        "assets": score_assets(vehicle),
    }

    contributions = {key: factor_scores[key] * WEIGHTS[key] for key in WEIGHTS}
    final_score = round(sum(contributions.values()), 2)
    risk_band = band_for_score(final_score)

    # Policy rules: a lender would not lend in these cases whatever else is true.
    overrides = []
    if monthly_income <= 0:
        overrides.append("No income in the last 6 months")
    else:
        if burden > LOAN_BURDEN_LIMIT:
            overrides.append(f"Loan payments would use more than {LOAN_BURDEN_LIMIT * 100:.0f}% of income")
        if residual < 0:
            overrides.append("Income would not cover essential costs and loan payments")
    if overrides:
        risk_band = "High Risk"

    if monthly_income <= 0:
        burden_text = "No income to measure loan payments against"
        disposable_text = "No income to measure"
    else:
        burden_text = (
            f"Existing loan payments Rs {existing_loan_payments:,.0f} plus the new installment "
            f"Rs {new_emi:,.0f} is {burden * 100:.0f}% of income"
        )
        if residual >= 0:
            disposable_text = f"Rs {residual:,.0f} left a month after essentials and loan payments"
        else:
            disposable_text = f"Short by Rs {-residual:,.0f} a month after essentials and loan payments"
        if floor_applied:
            disposable_text += " (essentials raised to the minimum for the household size)"

    details = {
        "loan_burden": burden_text,
        "disposable_income": disposable_text,
        "income_stability": (
            "No income to measure"
            if stability is None
            else f"Lowest month is {stability * 100:.0f}% of the average month"
        ),
        "income_per_person": f"Rs {per_person:,.0f} a month for each of {household_size} household members",
        "bills_on_time": f"{int(bills_on_time)} of {BILLS_WINDOW} bills paid on time",
        "failed_payments": f"{plural(int(failed_payments), 'failed payment')} in the last 6 months",
        "active_loans": f"{plural(int(active_loans), 'loan')} being repaid",
        "savings_cushion": f"Average balance covers {months_cushion:.1f} months of income",
        "time_in_work": f"{plural(int(months_in_work), 'month')} in current work",
        "assets": VEHICLE_LABELS[vehicle],
    }

    return {
        "final_score": final_score,
        "risk_band": risk_band,
        "breakdown": contributions,
        "details": details,
        "overrides": overrides,
        "loan_emi": round(new_emi, 2),
        "residual_income": round(residual, 2),
    }
