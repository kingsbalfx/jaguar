# System Architecture & Design Documentation

## Overview

This is a monorepo combining a **web platform** (Jaguar) and a **trading bot** (ICT Trading Bot) integrated via APIs and a shared Supabase database.

```
┌─────────────────────────────────────────────────────────────┐
│                    Users (Web Browser)                       │
└────────┬──────────────────────────────────────────────────┬──┘
         │                                                  │
    [Mentorship]                                   [Payment UI]
         │                                                  │
         └────────────────┬─────────────────────────────────┘
                          │
         ┌────────────────▼──────────────────────┐
         │    Jaguar Web Platform (Node/Next)    │
         │  ┌──────────────────────────────────┐ │
         │  │ Pages:                           │ │
         │  │ - Auth, Dashboard, Admin        │ │
         │  │ - Payments, Subscription        │ │
         │  │ - Analytics, Bot Logs           │ │
         │  └──────────────────────────────────┘ │
         │  ┌──────────────────────────────────┐ │
         │  │ APIs:                            │ │
         │  │ - init-paystack                  │ │
         │  │ - admin endpoints                │ │
         │  │ - bot logs, analytics            │ │
         │  └──────────────────────────────────┘ │
         └────────────┬──────────────┬────────────┘
                      │              │
         ┌───────────▼───┐    ┌─────▼──────────┐
         │  Paystack     │    │   Supabase     │
         │  (Payments)   │    │   (Database)   │
         │               │    │                │
         │ - Checkout    │    │ Tables:        │
         │ - Webhook     │    │ - profiles     │
         │               │    │ - payments     │
         └───────────────┘    │ - subscriptions│
                              │ - bot_logs    │
                              │ - ...         │
                              └─────▲─────────┘
                                    │
         ┌──────────────────────────┘
         │
         │ Persistence / Integrations:
         │ - Bot writes to Supabase `bot_signals` and `bot_logs`
         │ - /api/paystack-webhook (payments)
         │ - Control API
         │
         │
    ┌────▼──────────────────────────┐
    │  Trading Bot (Python)          │
    │  ┌────────────────────────────┐│
    │  │ Core:                      ││
    │  │ - MT5 Connector            ││
    │  │ - Strategy Engine          ││
    │  │ - Risk Management          ││
    │  └────────────────────────────┘│
    │  ┌────────────────────────────┐│
    │  │ APIs:                      ││
    │  │ - Flask health endpoint    ││
    │  │ - /control endpoint        ││
    │  │ - Log persistence          ││
    │  └────────────────────────────┘│
    │                                 │
    │  Signals:                        │
    │  - Buy/Sell trades              │
    │  - Risk alerts                  │
    │  - Log events                   │
    └─────────────────────────────────┘
```

## Data Flow

### Trade Execution Flow
1. Bot analyzes market using ICT strategy
2. Bot executes trade on MT5
3. Bot persists the signal to Supabase (`bot_signals` / `bot_logs`) after analysis
4. Web server (Jaguar) reads from Supabase for admin views and may broadcast via WebSocket for live dashboards
5. Admin sees live trade in dashboard populated from Supabase
6. Bot logs event to Supabase for audit trail

### Payment Flow
1. User clicks "Subscribe" button on web
2. UI shows `/subscribe` page
3. User enters email and clicks "Buy"
4. UI calls POST /api/init-paystack with email + amount
5. API returns Paystack authorization URL
6. User is redirected to Paystack payment gateway
7. User completes payment on Paystack
8. Paystack sends webhook POST /api/paystack-webhook with signature
9. Web app validates signature and processes charge.success event
10. Web updates profiles.lifetime = true for that email
11. User now has lifetime access (bot works)

### Admin Dashboard Flow
1. Super admin logs in (Supabase auth)
2. Admin checks role (must be "admin")
3. Can view:
   - All users and toggle lifetime access
   - Payment history from Supabase
   - Bot activity logs (real-time from logs table)
   - Trade analytics (win rate, P&L, etc.)

## Technology Stack

| Layer | Tech | Purpose |
|-------|------|---------|
| Frontend | Next.js, React | User interface & admin dashboard |
| Backend | Node.js, Express-like | API routes, Paystack webhook, auth |
| Database | Supabase (PostgreSQL) | Users, payments, logs |
| Auth | Supabase Auth | User session management |
| Payments | Paystack | Payment processing |
| Bot | Python 3.11 | Trading strategy, MT5 |
| Webhooks | HMAC-SHA256/512 | Secure event delivery |
| ORM | Supabase JS SDK | Database queries |
| Real-time | WebSocket | Live trade updates |
| Deployment | Docker | Containerized services |

## Database Schema (Supabase)

### profiles
- id (UUID, PK)
- email (VARCHAR)
- name (VARCHAR)
- role (ENUM: admin, user, vip)
- lifetime (BOOLEAN, default false)
- created_at (TIMESTAMP)

### payments
- id (UUID, PK)
- event (VARCHAR, e.g., "charge.success")
- data (JSONB, Paystack event payload)
- customer_email (VARCHAR, FK to profiles.email)
- amount (INTEGER, in kobo/cents)
- status (VARCHAR)
- received_at (TIMESTAMP)

### subscriptions
- id (UUID, PK)
- email (VARCHAR, FK profiles.email)
- plan (VARCHAR, e.g., "lifetime")
- status (VARCHAR, e.g., "active", "revoked")
- amount (INTEGER)
- started_at (TIMESTAMP)
- ended_at (TIMESTAMP, nullable)

### bot_logs
- id (UUID, PK)
- event (VARCHAR, e.g., "trade_pushed")
- payload (JSONB, event data)
- created_at (TIMESTAMP)

## Security Model

### Authentication
- Supabase Session-based auth for web users
- Role-based access control (RBAC) for admin pages
- x-admin-secret header for non-session admin endpoints

### Paystack Webhook
- Incoming Paystack webhook signed with HMAC
- Signature verified with timing-safe comparison
- Prevents replay and tamper attacks

### Secrets
- All app secrets in environment variables (never hardcoded)
- MT5 credentials stored in Supabase `mt5_credentials` (admin-only)
- `.gitignore` prevents `.env` from being committed
- Service role key only on server side
- Public anon key safe for client

## Scalability Considerations

1. **Database**: Supabase handles horizontal scaling
2. **APIs**: Stateless Node.js services (auto-scale with Docker Swarm/K8s)
3. **Bot**: Currently single instance; can be replicated with shared queue (Redis)
4. **Webhooks**: Implement retry logic + queue (Bull, RabbitMQ) for high volume
5. **WebSocket**: Use Redis pub/sub for multi-instance broadcasting

## Monitoring & Observability

- Structured JSON logging with timestamps and levels
- Error tracking (Sentry integration ready)
- Request latency tracking
- Trade metrics dashboard
- Admin can view bot logs in real time

## Deployment

- Docker Compose for local development
- Production: Kubernetes or managed container service
- Database: Supabase hosted / self-hosted PostgreSQL
- CI/CD: GitHub Actions for automated testing and deployment

---

**Last Updated**: Feb 10, 2026


