# WatchlistAPP

A procurement request system for retail stores. Replaces the back-and-forth WhatsApp/iMessage chaos of "we're running low on iPhone 15 cases" with a clean, trackable workflow.

## What it does

- **Manager** sees they're running low on stock → submits a request via web app
- **Buyer** (the person who actually places orders) gets notified, sees the queue, marks items as ordered
- **Manager** gets notified when their request is fulfilled
- Everyone has a clear audit trail instead of lost messages

## Stack

- **Backend:** FastAPI + SQLAlchemy + PostgreSQL
- **Auth:** JWT with role-based access (manager / buyer)
- **Notifications:** Email-to-SMS gateways (free) via Resend
- **Frontend:** React + Vite + Tailwind (mobile-first)
- **Hosting:** Fly.io (backend) + Supabase (DB) + Vercel (frontend)

## Local setup

```bash
# Clone and enter
git clone <repo-url>
cd rmb-restock

# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your DB URL and secrets

# Run migrations
alembic upgrade head

# Seed initial data (sample products + admin user)
python -m app.seed

# Start the server
uvicorn app.main:app --reload
```

API will be available at `http://localhost:8000`. Swagger docs at `http://localhost:8000/docs`.

## Running tests

```bash
pytest
```

## Project structure

```
rmb-restock/
├── app/
│   ├── core/          # Config, security (JWT, hashing), DB setup
│   ├── models/        # SQLAlchemy ORM models
│   ├── schemas/       # Pydantic request/response schemas
│   ├── routers/       # API route handlers
│   ├── services/      # Business logic (notifications, etc.)
│   └── main.py        # FastAPI app entrypoint
├── tests/             # pytest tests
├── requirements.txt
├── .env.example
└── README.md
```

## Design choices

- **PostgreSQL** over MongoDB because the data is highly relational (users → requests → status history) and we need transactional integrity when status changes.
- **JWT auth** over sessions because the frontend is a separate SPA and we'll likely want mobile clients later.
- **Email-to-SMS gateways** over Twilio because cost is a hard constraint for v1. Easy to swap in Twilio later by changing one service module.
- **Soft-delete pattern** on requests (status='cancelled') instead of hard delete, so we keep a full audit trail.

## Roadmap

- [x] v1: Core CRUD + auth + SMS notifications
- [ ] v2: WhatsApp notifications instead of email-to-SMS
- [ ] v3: Inventory tracking (auto-suggest restock based on sales velocity)
- [ ] v4: Supplier integrations (auto-place orders via supplier APIs)
