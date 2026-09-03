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
    deals,
    orders,
    cart,
    checkout,
    chat,
    b2b,
    messaging,
    negotiation,
    seller,
    payments,
    voice,
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
api_router.include_router(deals.router)
api_router.include_router(orders.router)
api_router.include_router(cart.router)
api_router.include_router(checkout.router)
api_router.include_router(chat.router)
api_router.include_router(b2b.router)
api_router.include_router(messaging.router)
api_router.include_router(negotiation.router)
api_router.include_router(seller.router)
api_router.include_router(payments.router)
api_router.include_router(voice.router)
