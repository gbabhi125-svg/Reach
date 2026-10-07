# REACH — Recycle, Earn, Act, Care, Help

A waste-collection marketplace. Households list waste; once a village crosses a **quota**, the
nearest verified collector is notified and does one consolidated trip. Companies skip the quota and
schedule direct pickups. Every pickup is hash-chained and rolls up into waste-flow / ESG reports.

## Prerequisites
- Python 3.10+  (`python --version`)
- Node.js 18+   (`node --version`)

## Quick start

```bash
# 1. (recommended) create a virtualenv
python -m venv .venv
source .venv/bin/activate          # Windows:  .venv\Scripts\activate

# 2. install everything (Python deps + both Next.js apps) — one time
python install_all.py

# 3. run everything (6 backend APIs + 2 web apps)
python run_all.py
```

Open:
| What | URL |
|---|---|
| Generator app (households) | http://localhost:3001 |
| Collector app (kabadiwalas) | http://localhost:3002 |
| pricing-service API docs | http://localhost:8001/docs |
| generator-service | http://localhost:8002/docs |
| collector-service | http://localhost:8003/docs |
| pickup-service | http://localhost:8004/docs |
| data-layer-service | http://localhost:8005/docs |
| corporate-service | http://localhost:8006/docs |

Ctrl+C stops everything. Useful flags: `--backend` (APIs only), `--fresh` (wipe the dev database).

### Manual commands (if you prefer separate terminals)
```bash
pip install -r requirements.txt
uvicorn main:app --port 8001 --app-dir backend/pricing-service/src
uvicorn main:app --port 8002 --app-dir backend/generator-service/src
uvicorn main:app --port 8003 --app-dir backend/collector-service/src
uvicorn main:app --port 8004 --app-dir backend/pickup-service/src
uvicorn main:app --port 8005 --app-dir backend/data-layer-service/src
uvicorn main:app --port 8006 --app-dir backend/corporate-service/src
cd frontend/apps/generator && npm install && npm run dev     # :3001
cd frontend/apps/collector && npm install && npm run dev     # :3002
```
(Load `.env` yourself in this mode, e.g. `export $(grep -v '^#' .env | xargs)`. `run_all.py` does it for you.)

## Try it in the browser (mock mode — no accounts needed)
1. **Generator app** (:3001): enter any phone, press **Send OTP**. In mock mode no SMS is sent; the code is
   printed in the terminal running `run_all.py` (`[MOCK OTP] phone=... code=1234`). Enter it, then your name + village.
2. List waste: `plastic`, `80` kg. Three households at 80 kg (or one at 200 kg+) crosses the plastic quota and opens a run.
   To act as several households, use a private window per household, or call the API at :8002/docs.
3. **Collector app** (:3002): phone, then OTP (again from the terminal), then name, then Aadhaar number **`999999990019`**
   (Setu's sandbox test number), then any OTP such as `0000`. You'll see the open run: **Accept**, enter weights, **Log pickup**, **Complete run**.
4. Corporate flow + reports are API-only for now: open http://localhost:8006/docs, `POST /corporates` with GSTIN `27AAICB3918J1CT`.

## Tests
```bash
python integration_test.py                       # in-process, no servers needed
python run_all.py --backend --fresh              # terminal 1
python live_smoke_test.py                        # terminal 2 — real HTTP against all 6 services
```
Both cover: geocoding, OTP signup, quota crossing, KYC gate, pickup, hash-chain, reports, corporate flow.

## Values to edit later (all are placeholders today)
| What | Where |
|---|---|
| Real provider keys (MSG91, Setu, Razorpay) | `.env`, then set `REACH_MOCK_EXTERNAL=0` |
| Your contact email for Nominatim | `.env` → `REACH_CONTACT_EMAIL` |
| Rate card (₹/kg) and quota thresholds (kg) | edit live: `PATCH http://localhost:8001/categories/plastic` body `{"rate_per_kg": 14, "quota_kg": 150}`; or change seed defaults in `backend/pricing-service/src/main.py` (only applies to a fresh DB) |
| Ports / URLs the web apps call | `frontend/apps/*/.env.local` |
| Allowed web origins (CORS) | `.env` → `REACH_CORS_ORIGINS` |
| Database | dev uses SQLite file `reach_dev.db`. For Postgres+PostGIS run `db/schema.sql`, then point `backend/shared/db.py` at it (`create_engine("postgresql://...")` + `pip install psycopg2-binary`) |

Rate card seeds are starting points from published household scrap rates; **e-waste (₹60/kg) is still a guess**, and
the quotas are untested economics. Confirm all of them with a local kabadiwala before the pilot.

## Project layout
```
reach/
├── run_all.py            # start everything          install_all.py      # one-time setup
├── integration_test.py   # in-process test           live_smoke_test.py  # real-HTTP test
├── requirements.txt      .env / .env.example
├── db/schema.sql         # production Postgres+PostGIS schema
├── docs/api-contracts.md # every endpoint, auto-generated
├── backend/
│   ├── shared/            db.py (models) geocode.py (Nominatim) otp.py (MSG91) kyc.py (Setu Aadhaar) gst.py (Setu GST)
│   ├── pricing-service/   :8001  rate card + quotas
│   ├── generator-service/ :8002  signup, postings, quota tracking, opens runs
│   ├── collector-service/ :8003  signup, Aadhaar KYC, open runs, accept, stop lists
│   ├── pickup-service/    :8004  log pickups (hash-chained), complete runs
│   ├── data-layer-service/:8005  cluster / region waste-flow reports
│   └── corporate-service/ :8006  GST-verified companies, direct pickups, own ESG report
└── frontend/apps/
    ├── generator/         :3001  Next.js
    └── collector/         :3002  Next.js
```

## Known gaps — read before putting this in front of real users
- **No API authentication.** Anyone who can reach the APIs can call them. Add login tokens (JWT/sessions) after OTP verification before any public deploy.
- Collectors currently see **all** open runs; nearest-first filtering isn't implemented yet (coordinates are stored, ready for it).
- The web apps remember the user in browser `localStorage`, not a real session.
- Photo upload isn't built (`photo_url` is just a string field). Payments (Razorpay) aren't wired; cash-on-pickup assumed.
- Corporate portal has no web UI yet (API only). The hash chain isn't safe against two simultaneous writes; fine for pilot volumes.
- CPCB EPR registration is a business/compliance step on their portal, not an API, so there's nothing to integrate in code.
- Real MSG91 / Setu / Nominatim calls are written but have **never been run against the live providers** (mock-tested only). Expect to adjust field names against each provider's current docs on the first real call.
