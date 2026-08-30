"""
App entrypoint. Run with:
    uvicorn app.main:app --reload
"""
import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine
from app.api.v1.router import api_router
from app.realtime.pipeline_ws import router as pipeline_ws_router
from app.realtime.deals_ws import router as deals_ws_router
from app.realtime.wallet_ws import router as wallet_ws_router
from app.realtime.notifications_ws import router as notifications_ws_router, manager as notification_manager
from app.db.runtime_migrations import apply_sqlite_compatibility_migrations, migrate_legacy_wallet_data
from app.services.deal_events import deal_event_bus
from app.services.deals_pipeline import bootstrap_deals_data, evaluate_deals, finalize_reversal_orders, release_expired_reservations
from app.services.budget_agent import evaluate_all_budget_matches
from app.core.database import SessionLocal
from app.core.rate_limit import SensitiveEndpointRateLimitMiddleware

# Import models so Base.metadata knows about every table before create_all runs.
import app.models  # noqa: F401

# TestClient and some WSGI probes do not enter lifespan; keep local SQLite
# structurally current at import time. This is a no-op for PostgreSQL.
apply_sqlite_compatibility_migrations(engine)
Base.metadata.create_all(bind=engine)
migrate_legacy_wallet_data(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev convenience — creates tables if they don't exist yet.
    # In production, use Alembic migrations instead (see README).
    apply_sqlite_compatibility_migrations(engine)
    Base.metadata.create_all(bind=engine)
    migrate_legacy_wallet_data(engine)

    def initialize_deals() -> list:
        db = SessionLocal()
        try:
            bootstrap_deals_data(db)
            finalize_reversal_orders(db)
            deal_events = [*release_expired_reservations(db), *evaluate_deals(db)]
            return [*deal_events, *evaluate_all_budget_matches(db)]
        finally:
            db.close()

    def run_deal_monitor_cycle() -> list:
        db = SessionLocal()
        try:
            finalize_reversal_orders(db)
            deal_events = [*release_expired_reservations(db), *evaluate_deals(db)]
            return [*deal_events, *evaluate_all_budget_matches(db)]
        finally:
            db.close()

    await deal_event_bus.start()
    initial_events = await asyncio.to_thread(initialize_deals)
    for event in initial_events:
        await deal_event_bus.publish(event.as_dict() if hasattr(event, "as_dict") else event)
        if isinstance(event, dict) and event.get("user_id"):
            await notification_manager.broadcast(event["user_id"], event)

    async def monitor_deals() -> None:
        while True:
            await asyncio.sleep(settings.DEAL_SCAN_INTERVAL_SECONDS)
            events = await asyncio.to_thread(run_deal_monitor_cycle)
            for event in events:
                await deal_event_bus.publish(event.as_dict() if hasattr(event, "as_dict") else event)
                if isinstance(event, dict) and event.get("user_id"):
                    await notification_manager.broadcast(event["user_id"], event)

    monitor_task = asyncio.create_task(monitor_deals(), name="astra-deal-trust-agent")
    app.state.deal_event_bus = deal_event_bus
    try:
        yield
    finally:
        monitor_task.cancel()
        with suppress(asyncio.CancelledError):
            await monitor_task
        await deal_event_bus.stop()


app = FastAPI(title=settings.APP_NAME, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SensitiveEndpointRateLimitMiddleware)

app.include_router(api_router)
app.include_router(pipeline_ws_router)
app.include_router(deals_ws_router)
app.include_router(wallet_ws_router)
app.include_router(notifications_ws_router)


@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.APP_NAME}
