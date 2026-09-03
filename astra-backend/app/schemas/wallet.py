from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ConsentAuthorizationRequest(BaseModel):
    amount: float = Field(gt=0)
    auth_method: Literal["Voice", "OTP"]
    order_ref: str | None = None
    checkout_ref: str | None = None
    voice_transcript: str | None = None
    consent_id: str | None = None
    otp_code: str | None = Field(default=None, pattern=r"^\d{6}$")

    @model_validator(mode="after")
    def validate_payload(self):
        if bool(self.order_ref) == bool(self.checkout_ref):
            raise ValueError("Specify exactly one of order_ref or checkout_ref")
        if self.auth_method == "Voice" and not self.voice_transcript:
            raise ValueError("voice_transcript is required for Voice authorization")
        if self.auth_method == "OTP" and bool(self.consent_id) != bool(self.otp_code):
            raise ValueError("consent_id and otp_code must be supplied together when verifying OTP")
        return self


class ConsentAuthorizationResponse(BaseModel):
    consent_id: str
    status: Literal["challenge_sent", "approved"]
    auth_method: Literal["Voice", "OTP"]
    expires_in_seconds: int | None = None
    message: str
    dev_otp: str | None = None


class RemittanceDestinationOut(BaseModel):
    country_code: str
    currency: str
    payout_methods: list[Literal["bank", "wallet"]]


class RemittanceComplianceOut(BaseModel):
    kyc_required: bool
    sanctions_screening: Literal["not_started"]


class RemittanceContextOut(BaseModel):
    reference: str
    status: Literal["stub"]
    source_country: str
    source_currency: str
    destinations: list[RemittanceDestinationOut]
    required_recipient_fields: list[str]
    compliance: RemittanceComplianceOut
