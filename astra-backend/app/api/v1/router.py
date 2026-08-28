from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    home,
    products,
    astra_check,
    ai_assistant,
    approval,
    pipeline,
    goals,
    wallet,
    notifications,
    explore,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(home.router)
api_router.include_router(products.router)
api_router.include_router(astra_check.router)
api_router.include_router(ai_assistant.router)
api_router.include_router(approval.router)
api_router.include_router(pipeline.router)
api_router.include_router(goals.router)
api_router.include_router(wallet.router)
api_router.include_router(notifications.router)
api_router.include_router(explore.router)
