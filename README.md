# Brightloop Subscription Management System

A full-stack subscription and recurring-billing platform built for the Odoo Make-A-Ton 9.0 Kochi Hackathon 2026.

Brightloop covers the complete subscription lifecycle: products and variants, plans, taxes, discount rules, quotation templates, customer and staff management, subscription workflow, automated invoice generation, partial payments, and revenue/overdue reporting.

## Stack

| Layer | Technology |
| --- | --- |
| Backend | FastAPI, SQLAlchemy 2, SQLite, Pydantic, JWT (python-jose), bcrypt |
| Frontend | React 19, Vite, custom hash router, hand-written responsive CSS |
| Scheduling | APScheduler daily billing job (plus a manual billing-run button) |
| Reporting | JSON endpoints and CSV exports |

## Features

- **Roles**: admin, internal staff, and customer portal with server-side access checks.
- **Catalog**: products with variants, taxes (default tax support), billing plans (daily/weekly/monthly/yearly) with pause/renew/early-close flags and auto-close.
- **Discounts**: product-level and subscription-level percentage/fixed rules, date windows, usage limits, minimum purchase/quantity, applied proportionally and once per invoice.
- **Subscriptions**: draft → quotation → confirmed → active → closed workflow, pause/resume, renew, early-close rules, create from quotation template, optional expiry date.
- **Billing**: idempotent invoice generation per `(subscription, billing period)`, catch-up for missed periods, payment terms (`Immediate`, `Net 15/30/60`), tax and discount totals, auto-close on expiry.
- **Invoices**: draft/confirmed/paid/cancelled, confirm, send, cancel guard when payments exist, partial payments, printable invoice layout, overdue detection.
- **Payments**: multiple methods, partial collection, overpayment blocked, customer-scoped history.
- **Reports**: dashboard KPIs (active subscriptions, MRR, collected revenue, outstanding, overdue), active subscriptions, revenue collected, overdue invoices, CSV exports.
- **Auth**: signup, login, forgot/reset password with a development outbox, password policy (more than 8 characters with upper, lower, and special characters).

## Project structure

```
backend/
  app/
    main.py          FastAPI app, CORS, scheduler
    models.py        SQLAlchemy models and indexes
    billing.py       invoice generation, taxes, discounts, payments
    auth.py          JWT, bcrypt, role dependencies
    seed.py          demo data
    routers/         auth, users, customers, products, plans, discounts,
                     subscriptions/templates, invoices, payments, reports
frontend/
  src/
    App.jsx          role-based shell and hash routing
    api.js           fetch wrapper, session storage, formatting, CSV download
    hooks.js         useApi / useRoute / useDebounced
    auth.jsx         auth context
    components/ui.jsx
    pages/           Auth, Dashboard, Products, Plans, Taxes, Templates,
                     Discounts, Customers, Staff, Subscriptions,
                     SubscriptionDetail, Invoices, InvoiceDetail, Payments, Reports
```

## Run locally

### 1. Backend

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python seed.py
uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000
- OpenAPI docs: http://localhost:8000/docs
- Health check: http://localhost:8000/api/health

To reset the database, stop the server and delete `backend/brightloop.db` (and any `-shm`/`-wal` files), then run `python seed.py` again.

Optional large seed for performance testing:

```powershell
python seed.py --large
```

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

- App: http://localhost:5173
- The frontend calls `http://localhost:8000/api` by default. Override with `VITE_API_URL` if needed.

Production build:

```powershell
npm run build
npm run preview
```

## Demo credentials

| Role | Email | Password |
| --- | --- | --- |
| Admin | `admin@brightloop.com` | `Admin@12345` |
| Internal staff | `staff@brightloop.com` | `Staff@12345` |
| Customer | `customer@brightloop.com` | `Customer@12345` |

The customer login opens the portal with only that customer's subscriptions, invoices, and payments.

## Billing notes

- Invoices are idempotent: a unique `(subscription_id, billing_period_start)` constraint plus an existence check prevent duplicates.
- Running billing twice in a row returns `created: 0` on the second run.
- Each subscription bills every missed period up to today (safety cap of 1000 periods per subscription).
- Discount usage counters increment once per invoice they apply to.
- Cancelled invoices are excluded from revenue and cannot be paid; invoices with payments cannot be cancelled.
- Money is stored and calculated with `Decimal` and rounded half-up to two places.

## Useful commands

```powershell
# backend syntax/import check
python -c "import app.main"

# frontend lint and build
npm run lint
npm run build
```

## Notes

- Email delivery is simulated through the **Dev Outbox** (`/dev-outbox`) so password-reset and invoice-send flows are testable without SMTP.
- The database and development logs are local artifacts; do not commit them to production repositories.
