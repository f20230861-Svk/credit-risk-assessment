# Design decisions: what and why

This document explains what the scorecard measures and why, in the order a lender thinks. Every number in it is a setting of this prototype, chosen by judgement and checked against how lenders and the regulator actually work. Section 8 says how each number would be fitted on real repayment data.

## 1. The problem in a lender's terms

A household with no credit file has no bureau score, so a lender has to judge from other evidence. Repayment fails for two broad reasons: the household **cannot** pay, because too little is left after living costs and existing loans, or it **does not** pay, because of how it handles obligations. A shock, such as a slow month or a medical bill, turns the first into the second. So the scorecard asks three questions:

| Question | Factors | Share of the score |
|---|---|---|
| Can they afford it? | Loan burden, disposable income, income stability, income per person | 50% |
| Will they pay? | Bills paid on time, failed payments, active loans | 30% |
| What if something goes wrong? | Savings cushion, time in work, assets | 20% |

With no track record to look at, evidence of capacity carries the most weight. Willingness is shown by payment behaviour. Buffers decide how much a shock hurts. The ordering is the claim. The exact percentages are judgement.

## 2. The unit is the household

Lending to low-income borrowers in India is judged at the **household** level. The RBI's rules for microfinance define a household as a husband, wife and their unmarried children, and require lenders to assess *household* income. The scorecard therefore takes the household's income, size and costs, not just one person's earnings.

## 3. What is measured and why

| Factor | Measured as | Why it matters | Where the data would come from | Weight |
|---|---|---|---|---|
| **Loan burden** | Existing loan payments plus the new installment, as a share of household income. Full points at 30% or less, none at 50% | The regulator's own affordability test. For low-income households the RBI caps total monthly loan repayments, old and new, at 50% of monthly household income | Loan application, credit bureau report, bank statement | 15% |
| **Disposable income** | What is left of income after essential costs and all loan payments, as a share of income. Full points at 20% or more, none at zero | Loan burden ignores living costs. A household can pass the 50% test and still be unable to eat. This is the cash-flow question a careful lender asks | Bank statement, household survey | 15% |
| **Income stability** | The lowest month's income divided by the average month, over 6 months | An average hides bad months, and the installment falls due in every month, including the worst one. Regularity of cash flow is a standard parameter in microfinance credit assessment | Bank credits over 6 months | 15% |
| **Income per person** | Household income divided by household size. ₹12,500 a person earns full points | Total income means little without knowing how many people it supports. Per-capita income is the standard poverty-line measure | Bank statement, household size | 5% |
| **Bills paid on time** | Utility, rent and phone bills paid by the due date, out of the last 12 | The closest substitute for a repayment history: small, regular obligations met on time | Utility and telecom payment records, with consent | 15% |
| **Failed payments** | Bounced automatic payments in 6 months. None is 100, one is 60, two is 30, three or more is 0 | A direct sign of a missed obligation. One is a warning, not a verdict | Bank statement | 8% |
| **Active loans** | Loans being repaid now, from any lender. None is 100, one 85, two 60, three 30, four or more 0 | Over-indebtedness is the failure mode of low-income lending. A study of 210 borrowing households in Tamil Nadu found that the number of credit arrangements, low household income and adverse shocks raise the likelihood of over-indebtedness | Credit bureau report | 7% |
| **Savings cushion** | Average month-end balance, in months of income. Three months earns full points | Money in hand absorbs a bad month before it becomes a missed payment | Bank statement | 10% |
| **Time in work** | Months with the same employer or platform. 24 months earns full points | Continuity of income. A long stint suggests income is likely to continue | Employer or platform record | 5% |
| **Assets** | Vehicle owned: none 0, cycle 25, bike or scooter 60, second-hand car 80, car 100 | A sign of stability and something of value, used in microfinance-style scoring. Small on purpose, see section 7 | Registration record or declaration | 5% |

### Essential costs have a floor

People tend to understate what they spend. So the scorecard uses the declared essential costs (food, rent, school, medical, transport) or **₹3,000 per household member**, whichever is higher, and the page says when the floor was applied. This is how household size enters the affordability test without penalising anyone: it raises the cost of living, and nothing else. The ₹3,000 is a prototype setting. A real lender would take it from local consumption data.

### The loan asked for changes the answer

Affordability depends on the loan, not only on the household, so the scorecard takes the **amount, tenure and interest rate** and works out the monthly installment with the standard formula (EMI = P × r × (1 + r)^n ÷ ((1 + r)^n − 1), with r the monthly rate). The same steady household scores 89.48 (Low Risk) for a ₹60,000 loan and is set to High Risk when asking for ₹3,00,000, because loan payments would then use 75% of its income. A tool that ignores the loan requested cannot make that distinction.

## 4. Policy rules sit outside the score

A weighted score lets strengths offset a fatal weakness. Three cases are too serious for that, so a rule sets the band to High Risk whatever the score is:

1. **No income in the last 6 months.** A household with a spotless record and no income still earns 40 points, and no lender would approve on that basis.
2. **Loan payments above 50% of household income.** This is the RBI's limit for low-income households. The prototype applies it to every household, which is the cautious choice.
3. **Income that does not cover essential costs plus loan payments.** If the money runs out before the month does, a good record cannot rescue the loan.

Points and rules work together. As loan burden rises from 30% to 50% the score falls to zero for that factor. Above 50% the answer no longer depends on anything else.

## 5. What was left out, and why

Banks collect far more than they score. Application forms run long because of identity checks (KYC), regulation, verification and product rules. A scorecard then keeps the 10 to 30 variables that carry real predictive power. More questions cost more than they give: borrowers drop out of long forms, data is missing, a model with no outcome data has nothing to learn the extra fields from, every field must be explained to the borrower, and each one needs consent and a fairness review. So the design adds a question only when it changes a lending decision.

| Considered | Decision | Reason |
|---|---|---|
| **Gender, caste, religion, marital status** | Not collected, not used | The RBI's fair practices guidelines say lenders must not discriminate on grounds of sex, caste and religion |
| **Urban or rural** | Collected, **never scored** | Location is a proxy for income, caste and religion, and scoring on it can amount to indirect discrimination. Rural life is already captured by measuring income *stability*. The area is stored only so that outcomes can be compared across areas, which the app's fairness check does |
| **Age** | Not scored | Age is an eligibility check (a minimum and a maximum at the end of the loan), not a measure of repayment behaviour |
| **Number of earning members** | Not scored yet | Sa-Dhan's credit assessment framework for microfinance uses it, so it is a real candidate. It would need validating against outcomes, and it could disadvantage single-earner households, which is a fairness concern |
| **Family size and dependents** | Used only for living costs and income per person | Household size raises what essentials cost. It is not a penalty for having a family |
| **Education level** | Left out | Weak link to repayment once income and record are known, and it can proxy for background |
| **Social or network signals** | Dropped after an early draft | Weak evidence and the highest fairness risk |
| **Mobile recharge patterns** | Dropped | Weak signal that overlaps with bills paid on time |
| **Loan purpose** | Left out | The RBI removed end-use restrictions on microfinance loans, and a stated purpose is easy to misreport |
| **Credit bureau score** | Not an input | These borrowers have none. The bureau's *counts* (active loans, existing payments) are used |
| **Fraud and identity checks** | A separate layer | Verification decides whether the inputs are true. It does not belong inside the risk score |

## 6. Why a scorecard first, and not a trained model

1. **There are no repayment outcomes yet.** A trained model needs households that repaid or defaulted to learn from.
2. **A lender must give reasons.** In a scorecard every point traces to a fact, so the breakdown is the reason. Some NBFCs' published fair-practice codes commit them to telling a borrower why a loan was refused.
3. **It can be audited and challenged.** A person can check every rule.
4. **It is the normal baseline.** Trained models are compared against a scorecard, and are adopted only if they beat it and can still explain themselves.

## 7. Responsible AI and fairness

- **Explainable:** every point of the score traces to a fact, and the breakdown doubles as the reason for the decision.
- **The AI explains and never decides.** It sees numbers only, never a name or identifier. The code, not the AI, picks the strongest factor and the biggest shortfall. It cannot change the score, and it is told not to recommend approving or rejecting. If it fails, a built-in explanation appears. Its text is labelled as AI-written.
- **A human decides.** The tool advises and the lender decides.
- **No protected attribute is an input,** and the area type is stored only for auditing. A test proves that changing the area type does not change a score.
- **Proxies are the real risk.** Vehicle ownership differs by gender and region. Time in work penalises new entrants. Income per person changes with household size. So assets, time in work and income per person carry 5% each, and a real deployment would compare approval and default rates across groups and remove any factor that shows a disparity it cannot justify.
- **A financed vehicle is a debt.** A vehicle with a running loan is counted in existing loan payments, so it cannot flatter the household twice.
- **Privacy:** collect only with consent, send only numbers to the AI service, and follow India's data-protection law.

## 8. Where the data would come from, and how the numbers would be fitted

**Sources.** India's Account Aggregator framework, regulated by the RBI, lets a person share financial data with a lender through a licensed consent manager, with explicit, revocable consent. It has been live since September 2021 and is the natural source for income, balance, existing payments and bounced payments. Credit bureaus give loan counts. Utility, telecom and rent records need consented partner data, which is an assumption to confirm. In this prototype a loan officer types the numbers in, which is the largest gap between the prototype and a real system. Every field in the form says where its value would come from.

**Fitting the numbers on real data:**

1. Collect outcomes for a pilot loan book, with default defined as, for example, 90 days overdue.
2. Test each factor's ability to separate good from bad borrowers, then fit a logistic regression and compare it with a gradient-boosted model.
3. Measure **ranking power** (Gini, KS), **stability over time** (population stability index) and **calibration** (predicted against actual default rates).
4. Set the band cut-offs so each band matches a default rate the lender can accept.
5. Deal with **reject inference**: rejected applicants never show an outcome, which biases the data.
6. Run the fairness check on real outcomes, then monitor for drift and re-fit on a schedule.

## 9. What this is not

- It has **not been validated on real data**, and its scores are not probabilities of default.
- The inputs are **typed in**, so nothing checks that they are true. A real system verifies income and guards against fraud.
- The fairness table has **a handful of demo rows**. It shows the mechanism, not evidence.
- The AI runs on a **free tier** with strict rate limits, and a production version would need an approved model and a data agreement.
- The weights and thresholds are **judgement**, not fitted values.

## Sources checked

- Reserve Bank of India, Master Direction on the Regulatory Framework for Microfinance Loans, 2022: household loan repayments capped at 50% of monthly household income, and a board-approved policy to assess household income. https://website.rbi.org.in/documents/d/rbi/89mdregulatoryframework17072025
- Reserve Bank of India, FAQs on that framework: the 50% limit also applies to non-microfinance loans given to low-income households. https://rbi.org.in/commonman/Upload/English/FAQs/PDFs/RFML30012025.pdf
- Reserve Bank of India, Guidelines on Fair Practices Code for Lenders, 2003: lenders must not discriminate on grounds of sex, caste and religion. https://website.rbi.org.in/documents/87730/39872377/36102.pdf
- Puliyakot, S., "Determinants of Overindebtedness among Microfinance Borrowers", Asia-Pacific Sustainable Development Journal, vol. 27, no. 1: the number of credit arrangements, low household income and adverse shocks raise the likelihood of over-indebtedness. https://www.unescap.org/sites/default/files/APSDJ%20Vol.27%20No.1_pp.20-41.pdf
- SIDBI, "Cash Flow Estimation for Responsible Lending": over-indebtedness stems from imprecise estimates of household income and cash flow. https://sidbi.in/uploads/coca_reports/Cash-Flow-Estimation-for-Responsible-Lending.pdf
- The Telegraph (Kolkata), 21 February 2022, on Sa-Dhan's credit assessment framework, which assesses income and expenditure using parameters such as the number of earning members and regularity of cash flows. https://obeta.ttef.in/business/norms-to-evaluate-small-borrowers/cid/1852791
- L&T Finance, "What is FOIR": lenders in India generally accept a fixed-obligations-to-income ratio of about 40% to 60%, depending on income and loan size. https://www.ltfinance.com/blog/foir-impact-personal-loan-approval
- Godrej Capital, "What is FOIR": limits tend to be more conservative for lower incomes. https://www.godrejcapital.com/media-blog/knowledge-centre/what-is-foir
- Department of Financial Services, Government of India, "Account Aggregator framework". https://financialservices.gov.in/beta/en/account-aggregator-framework
