from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class GoalOut(BaseModel):
    id: int
    name: str
    target_amount: float
    allocated_amount: float
    remaining_amount: float
    percent_funded: float
    deadline: str | None = None
    cadence_amount: float | None = None
    cadence_period: Literal["weekly", "monthly"] | None = None

    model_config = ConfigDict(from_attributes=True)


class GoalCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    target_amount: float = Field(gt=0)
    deadline: str | None = None  # ISO date string, e.g. "2026-12-31"
    cadence_amount: float | None = Field(default=None, ge=0)
    cadence_period: Literal["weekly", "monthly"] | None = None


class GoalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    target_amount: float | None = Field(default=None, gt=0)
    deadline: str | None = None
    cadence_amount: float | None = Field(default=None, ge=0)
    cadence_period: Literal["weekly", "monthly"] | None = None


class AllocateFundsRequest(BaseModel):
    """Moves money from the wallet's free balance into a goal's saved amount."""
    amount: float = Field(gt=0)


class WalletOut(BaseModel):
    available_balance: float
    available_balance_display: str   # "Rs. 135,000"

    model_config = ConfigDict(from_attributes=True)


class GoalsWalletRailOut(BaseModel):
    """Combined payload — exactly what the GoalsWalletRail component renders."""
    primary_goal: GoalOut | None
    wallet: WalletOut


class WalletLedgerEntryOut(BaseModel):
    id: int
    label: str
    amount: float
    entry_type: Literal["credit", "debit"]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WalletDetailOut(BaseModel):
    available_balance: float
    available_balance_display: str
    ledger: list[WalletLedgerEntryOut]


class WalletTopUpRequest(BaseModel):
    amount: float = Field(gt=0)
    label: str = "Wallet top-up"


class WalletWithdrawRequest(BaseModel):
    amount: float = Field(gt=0)
    label: str = "Wallet withdrawal"
