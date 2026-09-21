# Credit risk assessment for borrowers without a credit file

A working prototype for **AI-Powered Financial Inclusion: Dynamic Risk Assessment for Underserved Segments**. It scores a borrower who has no credit history from nine facts about their income, loans and payment record, shows how much each factor contributed, and has an AI write a short plain-language explanation, so a loan officer can explain the decision.

Author: Souvik Mondal

## Live demo

| | Link |
|---|---|
| Web app | https://credit-risk-app-yhpd.onrender.com |
| API and interactive docs | https://credit-risk-api-4i8w.onrender.com/docs |
| Source code | https://github.com/f20230861-Svk/credit-risk-assessment |

The app needs a login. The demo username and password are in the submission email, and are deliberately not written in this public repository.

The servers run on a free plan and sleep when idle. **The first request after a quiet period can take up to a minute.** Open the web app a couple of minutes before a demo.

## What it does

1. A loan officer signs in.
2. They enter nine facts about a borrower, or pick one of four example borrowers.
3. The API returns a score out of 100, a risk band (Low, Medium or High), and the points each factor added.
4. An AI (a large language model) turns the numbers into a short plain-language explanation: which factors helped, which held the score back, and how far the borrower is from the next band. If the AI is unavailable, the app shows a built-in explanation instead.
5. Every assessment is saved to a PostgreSQL database and shown in a history table.

## Architecture

```mermaid
flowchart TD
    U["Loan officer<br/>(browser)"] --> F["Frontend<br/>HTML, CSS, JavaScript<br/>Render static site"]
    F -->|"HTTPS + bearer token"| B["Backend API<br/>FastAPI<br/>Render web service"]
    B --> M["Scoring model<br/>weighted scorecard<br/>model.py"]
    B -->|"numbers only"| L["AI explanation<br/>Gemini API<br/>explain.py"]
    B -->|"SQL over TLS"| D[("PostgreSQL<br/>Neon")]
```

| Layer | Technology | Where it lives |
|---|---|---|
| Frontend | HTML, CSS and JavaScript, no framework | `frontend/index.html`, hosted on Render (static site) |
| Backend API | Python, FastAPI, Pydantic validation | `backend/main.py`, hosted on Render (web service) |
| Scoring | Weighted scorecard, per-factor breakdown | `backend/model.py` |
| AI explanation | LLM (Google Gemini API), optional, with a built-in fallback | `backend/explain.py` |
| Database | PostgreSQL on Neon | `backend/database.py` |
| Authentication | Signed JWT tokens (PyJWT) | `backend/main.py` |
| Tests | pytest, 94 tests | `backend/test_model.py`, `backend/test_auth.py`, `backend/test_explain.py` |

How a request flows:

1. The browser sends the username and password to `POST /login` and receives a token that lasts 12 hours.
2. The browser sends the nine facts to `POST /assess-risk` with the token.
3. The API checks the token, validates the inputs, computes the score, and saves the assessment to Postgres. It then asks the AI for a short explanation, sending only the numbers behind the score, and returns the result with its breakdown and the explanation.
4. `GET /history` returns recent assessments, again only with a valid token.

## How the score works

A lender asks three questions about a borrower. Can they afford the loan? Will they pay? What happens if something goes wrong? The scorecard turns nine facts into eight factors that answer those questions, then adds them up with fixed weights.

| Question | Factor | Measured as | Weight |
|---|---|---|---|
| Can they afford it? | Debt burden | Existing plus new loan installments as a share of income. Full points at 30% or less, none at 60% or more | 20% |
| | Income stability | The lowest month's income as a share of the average month over 6 months | 20% |
| | Income level | Average monthly income. ₹50,000 or more earns full points | 10% |
| Will they pay? | Bills paid on time | Utility, rent and phone bills paid by the due date, out of the last 12 | 20% |
| | Failed payments | Bounced automatic payments in 6 months: none is full points, then 60, 30 and 0 for three or more | 10% |
| What if something goes wrong? | Savings cushion | Average month-end balance in months of income. Three months earns full points | 10% |
| | Assets | Vehicle owned: none 0, cycle 25, bike or scooter 60, second-hand car 80, car 100 | 5% |
| | Time in work | Months with the same employer or platform. 24 months earns full points | 5% |

- **Risk bands:** 70 and above is Low Risk, 40 to below 70 is Medium Risk, below 40 is High Risk.
- **Policy rules.** Two facts force the band to High Risk whatever the score is, because a lender would not lend in either case: no income in the last 6 months, and loan payments that would use up all of the income. The app shows the rule when it applies.
- **A vehicle with a running loan** is counted under existing installments, because a financed vehicle is a debt and not only an asset.

Worked example, a steady earner (₹42,000 a month, lowest month ₹38,000, ₹7,000 of installments including the new one, 12 of 12 bills on time, no failed payments, ₹60,000 average balance, a bike, 36 months in work):
20 + 18.1 + 20 + 10 + 4.76 + 8.4 + 3 + 5 = **89.26, Low Risk**.

The four example borrowers in the app score 89.26 (Low), 60.86 (Medium), 15.66 (High), and a fourth with no income but a clean record, which scores 40 and is set to High Risk by the no-income rule.

The model is an **interpretable weighted scorecard with hand-set weights and thresholds**, not a machine-learning model trained on repayment data. That is a deliberate choice for the prototype: every point of the score can be traced to a fact, which is what a lender needs to explain a decision. See the next steps below for how it would become a trained model.

### The AI explains the score, it never decides it

The score and the band always come from the scorecard. The AI layer (`backend/explain.py`) receives only the numbers behind the score, meaning the points each factor earned and the facts behind them, with no names or identifiers. It writes 2 to 3 sentences for the loan officer. The prompt tells it not to change the score and not to recommend approving or rejecting a loan. The rest of the safeguards are in code:

- The AI only ever sees a copy of the result, so it cannot alter the saved or returned score.
- If the AI is off, slow (over 8 seconds), rate-limited or returns something unusable, the assessment still succeeds and the app shows its built-in explanation.
- The text is length-limited and displayed as plain text, never as HTML.
- The page labels an AI-written explanation as such.

## API

| Method | Path | Sign-in needed | Purpose |
|---|---|---|---|
| GET | `/` | No | Health check |
| POST | `/login` | No | Exchange username and password for a token |
| POST | `/assess-risk` | Yes | Score a borrower and save the assessment |
| GET | `/history?limit=20` | Yes | Recent assessments, newest first (limit 1 to 100) |

`/assess-risk` returns `final_score`, `risk_band`, `breakdown` (points per factor), `details` (the fact behind each factor), `overrides` (any policy rule that applied) and `ai_explanation`. The last is `null` when the AI layer is off or unavailable.

Inputs to `/assess-risk`, all required. Money is in rupees.

| Input | Meaning | Allowed |
|---|---|---|
| `monthly_income` | Average money received per month, last 6 months | 0 or more |
| `lowest_month_income` | Lowest month's income in the same period | 0 up to `monthly_income` |
| `existing_emi` | Monthly installments on loans already held | 0 or more |
| `requested_emi` | Monthly installment of the requested loan | 0 or more |
| `bills_on_time` | Bills paid by the due date, out of the last 12 | 0 to 12 |
| `failed_payments` | Bounced automatic payments in the last 6 months | 0 to 50 |
| `avg_balance` | Average month-end balance, last 6 months | 0 or more |
| `vehicle` | `none`, `cycle`, `two_wheeler`, `second_hand_car` or `car` | one of these |
| `months_in_work` | Months with the same employer or platform | 0 to 600 |

Anything else returns a 422 error.

## Security

- **No secrets in the code.** The database address, the login, and the token-signing key are read from environment variables. `.env` is git-ignored. `backend/.env.example` lists the names without values.
- **Protected endpoints.** `/assess-risk` and `/history` return 401 without a valid, unexpired token, because assessments contain applicants' financial details.
- **Tokens** are signed with HS256 and expire after 12 hours. Passwords are compared in constant time.
- **Fails closed.** If the login settings are missing, the server refuses to sign anyone in (503) instead of using defaults.
- **Input validation** with Pydantic on every request.
- **CORS** is restricted to the frontend's address in production through `ALLOWED_ORIGINS`.
- **Encrypted in transit:** the web app and API use HTTPS, and the database connection requires TLS.
- **Minimal data to the AI service.** Only numbers are sent, never names or identifiers. The API key is sent in a request header, not in a web address, so it never appears in logs. The free tier of the AI service may use prompts to improve the provider's products, which is one more reason to keep the request to anonymous numbers.

## How this maps to the brief

The company's brief lists what a strong prototype may include. This is where each item stands.

| The brief lists | What is built | Status |
|---|---|---|
| React JS user interface | Plain HTML, CSS and JavaScript web app | Simplified |
| Spring Boot or equivalent API service | FastAPI (Python) with generated OpenAPI docs at `/docs` | Equivalent |
| PostgreSQL for structured data | PostgreSQL on Neon, every assessment saved as a JSON document | Built |
| pgvector or a vector database, embeddings | Not built. Nothing in this problem needed it. See next steps | Not built |
| LLM service, prompt templates and guardrails | Gemini API, a prompt template in `explain.py`, guardrails in code | Equivalent |
| AWS or equivalent deployment | Render for the app and Neon for the database | Equivalent |
| Authentication, input validation, no hardcoded secrets | Signed tokens, Pydantic validation, environment settings, TLS | Built |
| Git, README, setup instructions, architecture diagram, tests | GitHub, this README, the diagram above, 94 tests | Built |
| Responsible AI, explainability and transparency | The AI explains the score and never decides it, and its text is labelled | Built |

## Run it locally

You need Python 3.9 or newer and a PostgreSQL database. A free Neon database works.

```bash
git clone https://github.com/f20230861-Svk/credit-risk-assessment.git
cd credit-risk-assessment/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then open .env and fill in your own values
uvicorn main:app --reload
```

The API is now at http://127.0.0.1:8000, with interactive docs at `/docs`.

For the frontend, open `frontend/index.html` and set `API_URL` near the top of the script to `"http://127.0.0.1:8000"`, then open the file in a browser.

### Settings

| Name | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `AUTH_USERNAME`, `AUTH_PASSWORD` | The account allowed to sign in |
| `JWT_SECRET` | Long random string used to sign tokens |
| `ALLOWED_ORIGINS` | Optional. Comma-separated websites allowed to call the API. Defaults to any |
| `GEMINI_API_KEY` | Optional. Key from Google AI Studio. Without it the AI explanation is off and the app uses its built-in one |
| `GEMINI_MODEL` | Optional. Defaults to `gemini-3.5-flash-lite` |

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -q
```

94 tests cover the scoring model (every factor on its own, worked examples, band boundaries, both policy rules, how the score should move, breakdown adding up to the score), authentication (missing, wrong, expired and forged tokens; wrong passwords; input validation, including a lowest month above the average), and the AI explanation (fallback on every failure, key never in the URL, prompt contents, the AI unable to change the score). The tests replace the database and the AI service with stand-ins, so they never touch real data or make real calls.

## Deployment

- **Database:** a Neon PostgreSQL project. The API creates the `assessments` table on startup.
- **Backend:** a Render web service with root directory `backend`, build command `pip install -r requirements.txt`, start command `uvicorn main:app --host 0.0.0.0 --port $PORT`, and the settings above as environment variables (`GEMINI_API_KEY` is optional).
- **Frontend:** a Render static site with publish directory `frontend`.
- Both services redeploy automatically when `main` is updated.

## Limitations and next steps

**Prototype limits**
- The nine facts are entered by hand. A real system would derive them from consented data such as bank and UPI transactions, utility and telecom records, and each one has a defined way of being measured, as in the table above.
- The weights and thresholds are hand-set judgement. The two policy rules are examples of the hard rules a lender applies before any score.
- There is one shared demo account, with its password held in an environment variable. A production version would keep hashed passwords in a users table, with roles and a limit on login attempts.

**AI explanation**
- It depends on a free-tier API with strict rate limits, so under heavy use most explanations would fall back to the built-in one. A production version would use a paid tier, a model approved for the lender, and a data-processing agreement.
- The AI's wording is checked only for length and presence. A production version would also check that every number it quotes matches the scorecard.
- Vector search and retrieval are not used. Nothing in this problem needed them. The natural next addition is embeddings with pgvector to retrieve the lender's policy text, so each reason can cite the rule behind it.

**From scorecard to trained model**
- Collect labelled repayment outcomes, then train and compare a logistic regression and a gradient-boosted model against this scorecard.
- Keep explanations, for example with SHAP values, so the per-factor breakdown survives the move to a trained model.
- Calibrate the scores to real default rates, and monitor for drift after launch.

**Fairness and privacy**
- Test every factor for bias against groups the lender must treat fairly. Assets, such as vehicle ownership, need particular care because ownership differs by gender, region and community, so it carries only 5% of the score.
- Obtain informed consent for alternative data and follow the applicable data-protection and digital-lending rules, for example India's DPDP Act.

## Repository layout

```
backend/
  main.py             API endpoints, login and token checks
  model.py            scoring model
  database.py         PostgreSQL connection and queries
  test_model.py       tests for the scoring model
  explain.py          optional AI-written explanation, with fallback
  test_auth.py        tests for sign-in and token checks
  test_explain.py     tests for the AI explanation
  requirements.txt    packages the deployed API needs
  requirements-dev.txt  extra packages for running the tests
  .env.example        the settings the API reads, without values
frontend/
  index.html          the web app
```

## How this was built

I built this with an AI assistant (Claude) to help write and debug the code, and I set up the accounts, ran and tested each part, and deployed it myself. Design decisions, such as choosing an explainable scorecard over an opaque model, are explained above.
