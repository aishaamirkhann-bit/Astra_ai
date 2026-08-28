from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.order import Order, OrderStatus
from app.models.user import User
from app.schemas.pipeline import PipelineStateOut
from app.services.pipeline_engine import PipelineEngine

router = APIRouter(prefix="/pipeline", tags=["Decision Pipeline"])


@router.get("/state", response_model=PipelineStateOut)
def get_pipeline_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Powers PipelineBar.tsx's node trail on Home."""
    order = (
        db.query(Order)
        .filter(Order.user_id == current_user.id)
        .filter(Order.status.in_([OrderStatus.PENDING_APPROVAL, OrderStatus.REVERSAL_WINDOW_OPEN]))
        .order_by(Order.created_at.desc())
        .first()
    )
    return PipelineEngine.build_state(order)
