from datetime import datetime, timedelta, timezone
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.security import generate_otp_code, hash_otp, verify_otp
from app.models.checkout import CheckoutSession
from app.models.order import Order, OrderStatus
from app.models.user import User
from app.models.wallet import FinancialConsentLog, UserWallet, WalletTransaction
from app.realtime.wallet_ws import manager
from app.schemas.goal import WalletDetailOut, WalletLedgerEntryOut, WalletOut, WalletTopUpRequest, WalletWithdrawRequest
from app.schemas.wallet import ConsentAuthorizationRequest, ConsentAuthorizationResponse, RemittanceContextOut
from app.services import astra_agents
from app.utils.helpers import as_aware_utc, format_pkr

router = APIRouter(prefix="/wallet", tags=["Wallet & Consent"])


def _detail(db: Session, user: User) -> WalletDetailOut:
    db.refresh(user.wallet)
    entries = db.query(WalletTransaction).filter(WalletTransaction.wallet_id == user.wallet.id).order_by(WalletTransaction.created_at.desc()).all()
    return WalletDetailOut(user_id=user.id, available_balance=user.wallet.available_balance, available_balance_display=format_pkr(user.wallet.available_balance), ledger=[WalletLedgerEntryOut.model_validate(entry) for entry in entries])


def _consent_subject(db: Session, user: User, payload: ConsentAuthorizationRequest) -> tuple[Order | None, CheckoutSession | None]:
    if payload.order_ref:
        order = db.query(Order).filter(Order.order_ref == payload.order_ref, Order.user_id == user.id).with_for_update().first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        if order.status != OrderStatus.PENDING_APPROVAL:
            raise HTTPException(status_code=409, detail="Order is no longer awaiting approval")
        if abs(order.price - payload.amount) > 0.01:
            raise HTTPException(status_code=409, detail="Consent amount does not match the order total")
        return order, None

    checkout = db.query(CheckoutSession).filter(
        CheckoutSession.checkout_ref == payload.checkout_ref,
        CheckoutSession.user_id == user.id,
    ).with_for_update().first()
    if not checkout:
        raise HTTPException(status_code=404, detail="Checkout session not found")
    if checkout.status != "awaiting_consent":
        raise HTTPException(status_code=409, detail="Checkout session is no longer awaiting consent")
    if as_aware_utc(checkout.expires_at) <= datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Checkout session expired")
    if abs(checkout.total - payload.amount) > 0.01:
        raise HTTPException(status_code=409, detail="Consent amount does not match the checkout total")
    return None, checkout


@router.get("", response_model=WalletDetailOut)
def get_wallet(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _detail(db, current_user)


@router.get("/summary", response_model=WalletOut)
def get_wallet_summary(current_user: User = Depends(get_current_user)):
    return WalletOut(available_balance=current_user.wallet.available_balance, available_balance_display=format_pkr(current_user.wallet.available_balance))


@router.get("/ledger", response_model=list[WalletLedgerEntryOut])
def get_ledger(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _detail(db, current_user).ledger


@router.get("/micro-settlements")
def micro_settlements(amount: float = 0, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if amount <= 0:
        latest = db.query(WalletTransaction).filter(WalletTransaction.wallet_id == current_user.wallet.id).order_by(WalletTransaction.created_at.desc()).first()
        amount = abs(latest.amount) if latest else 25000
    return astra_agents.micro_settlements(amount, f"wallet-{current_user.id}")


@router.get("/remittance-context", response_model=RemittanceContextOut)
def get_remittance_context(current_user: User = Depends(get_current_user)):
    return astra_agents.remittance_context(f"wallet-{current_user.id}")


@router.post("/topup", response_model=WalletDetailOut)
async def top_up(payload: WalletTopUpRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    wallet = current_user.wallet
    wallet.available_balance += payload.amount
    db.add(WalletTransaction(wallet_id=wallet.id, description=payload.label, amount=payload.amount, txn_type="Credit"))
    db.commit()
    result = _detail(db, current_user)
    await manager.balance_updated(current_user.id, result.available_balance, "Credit")
    return result


@router.post("/withdraw", response_model=WalletDetailOut)
async def withdraw(payload: WalletWithdrawRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    wallet = db.query(UserWallet).filter(UserWallet.id == current_user.wallet.id).with_for_update().one()
    if payload.amount > wallet.available_balance:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount exceeds your available wallet balance")
    wallet.available_balance -= payload.amount
    db.add(WalletTransaction(wallet_id=wallet.id, description=payload.label, amount=payload.amount, txn_type="Debit"))
    db.commit()
    result = _detail(db, current_user)
    await manager.balance_updated(current_user.id, result.available_balance, "Debit")
    return result


@router.post("/authorize-consent", response_model=ConsentAuthorizationResponse)
def authorize_consent(payload: ConsentAuthorizationRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    order, checkout = _consent_subject(db, current_user, payload)
    subject_matches = (
        FinancialConsentLog.reference_order_id == order.id
        if order
        else FinancialConsentLog.reference_checkout_id == checkout.id
    )

    if payload.auth_method == "Voice":
        spoken = re.sub(r"[^a-z0-9]", " ", payload.voice_transcript.lower())
        if "authorize" not in spoken or str(int(payload.amount)) not in spoken.replace(" ", ""):
            raise HTTPException(status_code=422, detail="Say the authorization phrase and exact payment amount")
        consent = FinancialConsentLog(
            user_id=current_user.id,
            amount=payload.amount,
            auth_method="Voice",
            voice_transcript=payload.voice_transcript,
            status="Approved",
            reference_order_id=order.id if order else None,
            reference_checkout_id=checkout.id if checkout else None,
        )
        db.add(consent)
        db.commit()
        db.refresh(consent)
        return ConsentAuthorizationResponse(consent_id=consent.consent_id, status="approved", auth_method="Voice", message="Voice authorization verified")

    if not payload.consent_id:
        code = generate_otp_code()
        consent = FinancialConsentLog(
            user_id=current_user.id,
            amount=payload.amount,
            auth_method="OTP",
            status="Flagged",
            reference_order_id=order.id if order else None,
            reference_checkout_id=checkout.id if checkout else None,
            otp_code_hash=hash_otp(code),
            otp_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        db.add(consent)
        db.commit()
        db.refresh(consent)
        return ConsentAuthorizationResponse(consent_id=consent.consent_id, status="challenge_sent", auth_method="OTP", expires_in_seconds=300, message="A 6-digit authorization code was sent", dev_otp=code if settings.APP_ENV != "production" else None)

    consent = db.query(FinancialConsentLog).filter(
        FinancialConsentLog.consent_id == payload.consent_id,
        FinancialConsentLog.user_id == current_user.id,
        FinancialConsentLog.auth_method == "OTP",
        subject_matches,
    ).with_for_update().first()
    if not consent or consent.status != "Flagged" or not consent.otp_code_hash:
        raise HTTPException(status_code=404, detail="Active OTP challenge not found")
    if consent.otp_attempts >= 5:
        raise HTTPException(status_code=429, detail="Too many OTP attempts")
    if abs(consent.amount - payload.amount) > 0.01 or as_aware_utc(consent.otp_expires_at) <= datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="OTP challenge expired or amount changed")
    consent.otp_attempts += 1
    if not verify_otp(payload.otp_code, consent.otp_code_hash):
        db.commit()
        raise HTTPException(status_code=422, detail="Incorrect authorization code")
    consent.status = "Approved"
    db.commit()
    return ConsentAuthorizationResponse(consent_id=consent.consent_id, status="approved", auth_method="OTP", message="OTP authorization verified")
