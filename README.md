# Credit risk assessment for borrowers without a credit file

A working prototype for **AI-Powered Financial Inclusion: Dynamic Risk Assessment for Underserved Segments**. It scores a borrower who has no credit history from five everyday financial signals, and shows how much each signal contributed to the score, so a loan officer can explain the decision.

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
2. They enter five signals for a borrower, or pick one of three example borrowers.
3. The API returns a score out of 100, a risk band (Low, Medium or High), and the points each signal added.
4. The app explains the result in plain words: the strongest signal, and how many points would move the borrower up a band.
5. Every assessment is saved to a PostgreSQL database and shown in a history table.

## Architecture

```mermaid
flowchart LR
    U["Loan officer<br/>(browser)"] --> F["Frontend<br/>HTML, CSS, JavaScript<br/>Render static site"]
    F -->|"HTTPS + bearer token"| B["Backend API<br/>FastAPI<br/>Render web service"]
    B --> M["Scoring model<br/>weighted scorecard<br/>model.py"]
    B -->|"SQL over TLS"| D[("PostgreSQL<br/>Neon")]
```

| Layer | Technology | Where it lives |
|---|---|---|
| Frontend | HTML, CSS and JavaScript, no framework | `frontend/index.html`, hosted on Render (static site) |
| Backend API | Python, FastAPI, Pydantic validation | `backend/main.py`, hosted on Render (web service) |
| Scoring and explanation | Weighted scorecard, per-signal breakdown | `backend/model.py` |
| Database | PostgreSQL on Neon | `backend/database.py` |
| Authentication | Signed JWT tokens (PyJWT) | `backend/main.py` |
| Tests | pytest, 24 tests | `backend/test_model.py`, `backend/test_auth.py` |

How a request flows:

1. The browser sends the username and password to `POST /login` and receives a token that lasts 12 hours.
2. The browser sends the five signals to `POST /assess-risk` with the token.
3. The API checks the token, validates the inputs, computes the score, saves the assessment to Postgres, and returns the result with its breakdown.
4. `GET /history` returns recent assessments, again only with a valid token.

## How the score works

The score is a weighted sum of five signals. Four are scored 0 to 100 by the input, and income is converted to a 0 to 100 score first.

| Signal | What it captures | Weight | Maximum points |
|---|---|---|---|
| Transaction regularity | How steadily money moves through the account | 30% | 30 |
| Utility bill payments | On-time payment of electricity, water, gas and phone bills | 25% | 25 |
| Monthly income | Average monthly inflow in rupees | 20% | 20 |
| Mobile usage stability | Consistency of recharge and usage patterns | 15% | 15 |
| Social signal | Community and network signals | 10% | 10 |

- **Income score** = `min(monthly income / ₹50,000, 1) × 100`. Income of ₹50,000 or more earns full points.
- **Risk bands:** 70 and above is Low Risk, 40 to below 70 is Medium Risk, below 40 is High Risk.

Worked example, a steady earner with signals 85, 90, ₹42,000, 80 and 70:
25.5 + 22.5 + 16.8 + 12 + 7 = **83.8, Low Risk**.

The model is an **interpretable weighted scorecard with hand-set weights**, not a machine-learning model trained on repayment data. That is a deliberate choice for the prototype: every point of the score can be traced to an input, which is what a lender needs to explain a decision. See the next steps below for how it would become a trained model.

## API

| Method | Path | Sign-in needed | Purpose |
|---|---|---|---|
| GET | `/` | No | Health check |
| POST | `/login` | No | Exchange username and password for a token |
| POST | `/assess-risk` | Yes | Score a borrower and save the assessment |
| GET | `/history?limit=20` | Yes | Recent assessments, newest first (limit 1 to 100) |

Inputs to `/assess-risk`: `txn_regularity`, `utility_payment_score`, `mobile_usage_stability` and `social_signal_score` (each 0 to 100), and `avg_monthly_inflow` (0 or more). Anything else returns a 422 error.

## Security

- **No secrets in the code.** The database address, the login, and the token-signing key are read from environment variables. `.env` is git-ignored. `backend/.env.example` lists the names without values.
- **Protected endpoints.** `/assess-risk` and `/history` return 401 without a valid, unexpired token, because assessments contain applicants' financial details.
- **Tokens** are signed with HS256 and expire after 12 hours. Passwords are compared in constant time.
- **Fails closed.** If the login settings are missing, the server refuses to sign anyone in (503) instead of using defaults.
- **Input validation** with Pydantic on every request.
- **CORS** is restricted to the frontend's address in production through `ALLOWED_ORIGINS`.
- **Encrypted in transit:** the web app and API use HTTPS, and the database connection requires TLS.

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

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -q
```

24 tests cover the scoring model (worked examples, band boundaries, income cap, breakdown adding up to the score) and authentication (missing, wrong, expired and forged tokens; wrong passwords; input validation). The auth tests replace the database with stand-ins, so they never touch real data.

## Deployment

- **Database:** a Neon PostgreSQL project. The API creates the `assessments` table on startup.
- **Backend:** a Render web service with root directory `backend`, build command `pip install -r requirements.txt`, start command `uvicorn main:app --host 0.0.0.0 --port $PORT`, and the settings above as environment variables.
- **Frontend:** a Render static site with publish directory `frontend`.
- Both services redeploy automatically when `main` is updated.

## Limitations and next steps

**Prototype limits**
- The five signals are entered by hand. A real system would derive them from consented data such as bank and UPI transactions, utility and telecom records.
- There is one shared demo account, with its password held in an environment variable. A production version would keep hashed passwords in a users table, with roles and a limit on login attempts.

**From scorecard to trained model**
- Collect labelled repayment outcomes, then train and compare a logistic regression and a gradient-boosted model against this scorecard.
- Keep explanations, for example with SHAP values, so the per-signal breakdown survives the move to a trained model.
- Calibrate the scores to real default rates, and monitor for drift after launch.

**Fairness and privacy**
- Test every signal, especially the social signal, for bias against groups the lender must treat fairly.
- Obtain informed consent for alternative data and follow the applicable data-protection and digital-lending rules, for example India's DPDP Act.

## Repository layout

```
backend/
  main.py             API endpoints, login and token checks
  model.py            scoring model
  database.py         PostgreSQL connection and queries
  test_model.py       tests for the scoring model
  test_auth.py        tests for sign-in and token checks
  requirements.txt    packages the deployed API needs
  requirements-dev.txt  extra packages for running the tests
  .env.example        the settings the API reads, without values
frontend/
  index.html          the web app
```

## How this was built

I built this with an AI assistant (Claude) to help write and debug the code, and I set up the accounts, ran and tested each part, and deployed it myself. Design decisions, such as choosing an explainable scorecard over an opaque model, are explained above.
