import asyncio
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.deal import DealDetail, DealListResponse, DealReservationResponse, ReserveDealRequest
from app.services.deal_events import DealLockTimeout, deal_event_bus
from app.services.deals_pipeline import get_deal_details, list_active_deals, reserve_deal

router = APIRouter(prefix="/deals", tags=["Deals"])


@router.get("", response_model=DealListResponse)
def get_deals(
    category: Literal["Tech", "Fashion", "Audio", "Accessories"] | None = None,
    sort_by: Literal["highest_discount", "top_trust"] = Query("highest_discount"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> DealListResponse:
    return list_active_deals(db, category, sort_by, page, page_size)


@router.get("/{deal_id}/details", response_model=DealDetail)
def get_deal_details_endpoint(deal_id: str, db: Session = Depends(get_db)) -> DealDetail:
    return get_deal_details(db, deal_id)


@router.post("/{deal_id}/reserve", response_model=DealReservationResponse)
async def reserve_deal_endpoint(
    deal_id: str,
    payload: ReserveDealRequest,
    current_user: User = Depends(get_current_user),
) -> DealReservationResponse:
    try:
        async with deal_event_bus.reservation_lock(deal_id):
            reservation, event = await asyncio.to_thread(reserve_deal, deal_id, payload, current_user.id)
    except DealLockTimeout as error:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(error)) from error
    await deal_event_bus.publish(event.as_dict())
    return reservation
