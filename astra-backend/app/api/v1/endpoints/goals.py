from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.goal import Goal
from app.models.user import User
from app.models.wallet import WalletLedgerEntry
from app.schemas.goal import (
    AllocateFundsRequest,
    GoalCreate,
    GoalOut,
    GoalsWalletRailOut,
    GoalUpdate,
    WalletOut,
)
from app.utils.helpers import format_pkr

router = APIRouter(prefix="/goals", tags=["Goals & Wallet"])


def _get_owned_goal(db: Session, goal_id: int, user: User) -> Goal:
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user.id).first()
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    return goal


@router.get("/rail", response_model=GoalsWalletRailOut)
def get_goals_wallet_rail(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Powers GoalsWalletRail.tsx on Home — the primary (first) goal + wallet balance."""
    primary_goal = (
        db.query(Goal).filter(Goal.user_id == current_user.id).order_by(Goal.id.asc()).first()
    )
    wallet = current_user.wallet

    return GoalsWalletRailOut(
        primary_goal=GoalOut.model_validate(primary_goal) if primary_goal else None,
        wallet=WalletOut(
            available_balance=wallet.available_balance,
            available_balance_display=format_pkr(wallet.available_balance),
        ),
    )


@router.get("", response_model=list[GoalOut])
def list_goals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full list — powers the /goals page (GoalManager)."""
    goals = db.query(Goal).filter(Goal.user_id == current_user.id).order_by(Goal.id.asc()).all()
    return [GoalOut.model_validate(g) for g in goals]


@router.post("", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
def create_goal(
    payload: GoalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = Goal(
        user_id=current_user.id,
        name=payload.name,
        target_amount=payload.target_amount,
        allocated_amount=0,
        deadline=payload.deadline,
        cadence_amount=payload.cadence_amount,
        cadence_period=payload.cadence_period,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return GoalOut.model_validate(goal)


@router.put("/{goal_id}", response_model=GoalOut)
def update_goal(
    goal_id: int,
    payload: GoalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = _get_owned_goal(db, goal_id, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    db.commit()
    db.refresh(goal)
    return GoalOut.model_validate(goal)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = _get_owned_goal(db, goal_id, current_user)

    # Anything already saved toward this goal goes back to the free wallet
    # balance instead of vanishing.
    if goal.allocated_amount > 0:
        wallet = current_user.wallet
        wallet.available_balance += goal.allocated_amount
        db.add(WalletLedgerEntry(
            wallet_id=wallet.id,
            label=f'Goal deleted — refund from "{goal.name}"',
            amount=goal.allocated_amount,
            entry_type="credit",
        ))

    db.delete(goal)
    db.commit()
    return None


@router.post("/{goal_id}/allocate", response_model=GoalOut)
def allocate_to_goal(
    goal_id: int,
    payload: AllocateFundsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Moves money from wallet.available_balance into goal.allocated_amount."""
    goal = _get_owned_goal(db, goal_id, current_user)
    wallet = current_user.wallet

    if payload.amount > wallet.available_balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount exceeds your available wallet balance",
        )

    wallet.available_balance -= payload.amount
    goal.allocated_amount += payload.amount

    db.add(WalletLedgerEntry(
        wallet_id=wallet.id,
        label=f'Contribution — {goal.name}',
        amount=-payload.amount,
        entry_type="debit",
    ))

    db.commit()
    db.refresh(goal)
    return GoalOut.model_validate(goal)
