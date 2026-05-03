# Watchlist

A lightweight procurement request system for small retail stores. Replaces ad-hoc messaging about restock needs with a clean, trackable workflow.

## Why it exists

In a small retail store, the manager constantly texts the buyer about restock needs throughout the day. Messages arrive one at a time, get lost in conversation, have no audit trail, and require back-and-forth to confirm what was handled. This app replaces that with a simple two-role system: the manager queues requests, the buyer gets one daily digest, one tap clears everything, and both sides get confirmation.

## How it works

1. **Manager** opens the app on their phone, taps "New Request"
2. Picks a product from the catalog (pre-loaded SKUs) or types a custom name, sets quantity, hits submit
3. Requests pile up as **PENDING** throughout the day — no notifications yet
4. Once a day at a configured time, the **buyer** receives **one SMS digest** with everything needed:
   ```
   Today's restock list (4 items):
   - 5x iPhone 15 Pro Case
   - 10x iPad Air Screen Protector
   - 3x AirPods Pro
   - 1x Custom item: anti-glare film
   Reply 'done' when handled or open the app.
   ```
5. Buyer taps **"Got everything"** in the app — one request clears all pending items at once
6. Manager gets an SMS confirmation when their requests are marked done
7. Anything still pending after **48 hours** auto-archives to DONE so the list never piles up forever

## Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI + SQLAlchemy + Pydantic |
| Database | PostgreSQL (production), SQLite (local dev) |
| Auth | JWT, role-based (manager / buyer), 30-day expiry |
| Notifications | Email-to-SMS gateways via Resend (free tier) |
| Tests | pytest, 23 tests, in-memory SQLite |

SMS is sent by emailing `{10-digit-phone}@{carrier-gateway}` — no Twilio account needed. The entire notifications module is one function to swap if we want to upgrade later.

## API endpoints

### Auth
| Method | Path | Who | Description |
|---|---|---|---|
| POST | `/auth/register` | Public | Create a new user account |
| POST | `/auth/login` | Public | JSON login, returns JWT |
| POST | `/auth/token` | Public | OAuth2 form login (used by Swagger UI) |

### Products
| Method | Path | Who | Description |
|---|---|---|---|
| GET | `/products` | Any | Browse catalog with optional category/search filters |
| POST | `/products` | Buyer | Add a new SKU to the catalog |
| GET | `/products/{id}` | Any | Get a single product |

### Requests
| Method | Path | Who | Description |
|---|---|---|---|
| POST | `/requests` | Manager | Submit a new restock request |
| GET | `/requests` | Any | List requests (managers see only their own) |
| POST | `/requests/clear-all` | Buyer | Mark all pending requests as DONE in one shot |
| POST | `/requests/send-digest` | Buyer | Manually trigger the daily SMS digest |
| POST | `/requests/archive-stale` | Buyer | Archive pending requests older than N hours (default 48) |
| GET | `/requests/{id}` | Any | Get a single request |
| PATCH | `/requests/{id}/status` | Buyer | Transition a request's status (pending → done) |
| DELETE | `/requests/{id}` | Any | Hard-delete a request (managers: own only) |

### Health
| Method | Path | Description |
|---|---|---|
| GET | `/health` | Returns `{"status": "ok"}` |

## Local setup

```bash
# 1. Clone and create a virtual environment
git clone <repo-url>
cd watchlist
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env — at minimum set SECRET_KEY to a random string

# 4. Seed sample data (8 products + a buyer account)
python -m app.seed
# Buyer login: phone=5555550100  password=changeme123

# 5. Start the server
uvicorn app.main:app --reload
```

Swagger UI at `http://localhost:8000/docs` — use the Authorize button with the buyer credentials above to explore the API interactively.

## Running tests

```bash
pytest -v
```

Expected output: **23 passed**. Tests run against an in-memory SQLite DB; no external services are hit (notifications are stubbed).

## Project structure

```
watchlist/
├── app/
│   ├── core/
│   │   ├── config.py       # Settings loaded from .env via pydantic-settings
│   │   ├── database.py     # SQLAlchemy engine + session factory
│   │   ├── deps.py         # FastAPI dependency helpers (get_current_user, require_role)
│   │   └── security.py     # JWT creation/decoding, bcrypt password hashing
│   ├── models/
│   │   ├── user.py         # User + UserRole enum
│   │   ├── product.py      # Product + ProductCategory enum
│   │   └── request.py      # Request, RequestHistory, RequestStatus enum
│   ├── schemas/
│   │   ├── user.py         # UserCreate, UserOut, TokenResponse
│   │   ├── product.py      # ProductCreate, ProductOut
│   │   └── request.py      # RequestCreate, RequestOut, status update + response schemas
│   ├── routers/
│   │   ├── auth.py         # /auth/register, /auth/login, /auth/token
│   │   ├── products.py     # /products CRUD
│   │   └── requests.py     # /requests workflow
│   ├── services/
│   │   ├── notifications.py  # SMS via email-to-SMS gateway (Resend)
│   │   └── archive.py        # Auto-archive stale pending requests
│   ├── seed.py             # One-time DB seed script
│   └── main.py             # FastAPI app, CORS, router registration
├── tests/
│   ├── conftest.py         # Fixtures: in-memory DB, test client, auth tokens
│   ├── test_auth.py        # Registration, login, validation
│   └── test_requests.py    # Full request lifecycle
├── requirements.txt
├── .env.example
└── README.md
```

## Design choices

**PostgreSQL over MongoDB** — the data is highly relational (users → requests → history entries) and status transitions need transactional integrity. A document store would require application-level joins with no real benefit.

**JWT over sessions** — the frontend is a separate SPA and we may add a React Native app later. Stateless tokens make that straightforward. The 30-day expiry is intentional: non-technical store staff on mobile hate re-logging in every day.

**Email-to-SMS gateways over Twilio** — zero cost at v1 scale. The entire send path is one function (`_send_sms_via_email`). Swapping to Twilio is a single module change.

**Daily digest over per-request notifications** — sending a text every time the manager submits a request would burn the buyer out fast. One summary at a configured time is more respectful of attention and mirrors how the store actually operates (one buying trip per day).

**Simplified two-state machine (pending / done)** — the original design had four states (pending → ordered → fulfilled → cancelled). Non-technical users won't navigate a four-state machine. "It's needed" and "it's handled" is all the workflow they need.

**Hard delete on `DELETE /requests/{id}`** — managers need to fix typos quickly without jumping through hoops. The `RequestHistory` table provides the audit trail; keeping zombie rows in `requests` just to preserve history is unnecessary overhead.

**Auto-archive at 48 hours** — a safety net for when the buyer forgets to tap "Got everything". Ensures the pending list reflects reality rather than accumulating stale items forever.

## What I'd improve with more time

- Wire `APScheduler` to call `send_daily_digest()` automatically at a configured hour — the endpoint exists, it just needs a trigger
- Wire `archive_stale_pending_requests()` to a daily cron job the same way
- Add inbound SMS parsing so the buyer can text "done" to clear the list (Twilio inbound webhooks)
- Build the React PWA frontend — the API is complete, currently accessible only via Swagger
- Full-text search on the product catalog — the current `ILIKE` doesn't handle run-together queries like "iphone12procase"
- Containerize with Docker + docker-compose for one-command local setup
- GitHub Actions CI to run pytest on every push
- Rate limiting on auth endpoints to prevent brute-force login attempts
- Migrate from SQLite to Supabase Postgres for production hosting

## Roadmap

- [x] v1: Backend — auth, catalog, requests, daily digest, auto-archive, 23 tests
- [ ] v2: React PWA frontend (mobile-first, works offline)
- [ ] v3: Production deployment (Fly.io + Supabase + Vercel)
- [ ] v4: SMS reply parsing for ultra-low-friction UX
