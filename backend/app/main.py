"""Main FastAPI application for Brightloop Subscription Management System."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import engine, SessionLocal, Base

# Import all models so tables get created
from app import models  # noqa: F401

from app.routers import auth, users, customers
from app.routers.products import products_router, taxes_router
from app.routers import plans, discounts
from app.routers.subscriptions import templates_router, subscriptions_router
from app.routers import invoices, payments, reports

settings = get_settings()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

scheduler = BackgroundScheduler()


def scheduled_billing():
    """Run billing from a scheduled context."""
    from app.billing import run_billing
    db = SessionLocal()
    try:
        result = run_billing(db)
        logger.info("Scheduled billing run: %s", result)
    except Exception as exc:
        logger.error("Scheduled billing error: %s", exc)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# App lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables
    Base.metadata.create_all(bind=engine)

    # Start scheduler (daily at midnight)
    scheduler.add_job(scheduled_billing, "cron", hour=0, minute=0)
    scheduler.start()
    logger.info("Scheduler started")

    yield

    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Brightloop Subscription Management System",
    description="A unified platform for managing subscriptions, billing, and revenue reporting.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
API_PREFIX = "/api"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(customers.router, prefix=API_PREFIX)
app.include_router(products_router, prefix=API_PREFIX)
app.include_router(taxes_router, prefix=API_PREFIX)
app.include_router(plans.router, prefix=API_PREFIX)
app.include_router(discounts.router, prefix=API_PREFIX)
app.include_router(templates_router, prefix=API_PREFIX)
app.include_router(subscriptions_router, prefix=API_PREFIX)
app.include_router(invoices.router, prefix=API_PREFIX)
app.include_router(payments.router, prefix=API_PREFIX)
app.include_router(reports.router, prefix=API_PREFIX)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "brightloop-sms"}


@app.get("/")
def root():
    return {"message": "Brightloop SMS API — see /docs for OpenAPI documentation"}


# ---------------------------------------------------------------------------
# Global error handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error("Unhandled error: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
