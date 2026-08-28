from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.wallet import WalletLedgerEntry
from app.schemas.goal import (
    WalletDetailOut,
    WalletLedgerEntryOut,
    WalletOut,
    WalletTopUpRequest,
    WalletWithdrawRequest,
)
from app.utils.helpers import format_pkr

router = APIRouter(prefix="/wallet", tags=["Goals & Wallet"])


@router.get("", response_model=WalletDetailOut)
def get_wallet(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Powers the /wallet page — balance + full ledger history."""
    wallet = current_user.wallet
    entries = (
        db.query(WalletLedgerEntry)
        .filter(WalletLedgerEntry.wallet_id == wallet.id)
        .order_by(WalletLedgerEntry.created_at.desc())
        .all()
    )
    return WalletDetailOut(
        available_balance=wallet.available_balance,
        available_balance_display=format_pkr(wallet.available_balance),
        ledger=[WalletLedgerEntryOut.model_validate(e) for e in entries],
    )


@router.get("/summary", response_model=WalletOut)
def get_wallet_summary(
    current_user: User = Depends(get_current_user),
):
    wallet = current_user.wallet
    return WalletOut(
        available_balance=wallet.available_balance,
        available_balance_display=format_pkr(wallet.available_balance),
    )


@router.get("/ledger", response_model=list[WalletLedgerEntryOut])
def get_ledger(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wallet = current_user.wallet
    entries = (
        db.query(WalletLedgerEntry)
        .filter(WalletLedgerEntry.wallet_id == wallet.id)
        .order_by(WalletLedgerEntry.created_at.desc())
        .all()
    )
    return [WalletLedgerEntryOut.model_validate(e) for e in entries]


@router.post("/topup", response_model=WalletDetailOut)
def top_up(
    payload: WalletTopUpRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """'Top Up' button on the Wallet page. In production this would sit
    behind a real payment gateway callback — here it credits directly,
    same as the seeded demo data does."""
    wallet = current_user.wallet
    wallet.available_balance += payload.amount

    db.add(WalletLedgerEntry(
        wallet_id=wallet.id,
        label=payload.label,
        amount=payload.amount,
        entry_type="credit",
    ))
    db.commit()

    return get_wallet(db=db, current_user=current_user)


@router.post("/withdraw", response_model=WalletDetailOut)
def withdraw(
    payload: WalletWithdrawRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """'Withdraw' button on the Wallet page."""
    wallet = current_user.wallet
    if payload.amount > wallet.available_balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount exceeds your available wallet balance",
        )

    wallet.available_balance -= payload.amount

    db.add(WalletLedgerEntry(
        wallet_id=wallet.id,
        label=payload.label,
        amount=-payload.amount,
        entry_type="debit",
    ))
    db.commit()

    return get_wallet(db=db, current_user=current_user)
