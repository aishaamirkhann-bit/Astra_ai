from typing import Literal
from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator

Role = Literal["buyer", "seller"]
CountryCode = Literal["PK", "CN", "IR", "AE"]


class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    preferred_language: str
    role: Role
    country: CountryCode = "PK"

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    role: Role = "buyer"
    preferred_language: str = "Roman Urdu"
    country: str = Field(default="PK", pattern=r"^(PK|CN|IR|AE)$")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Name must contain at least 2 non-space characters")
        return value

    @field_validator("country", mode="before")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        normalized = str(value or "PK").strip().upper()
        if normalized not in {"PK", "CN", "IR", "AE"}:
            raise ValueError("Country must be PK, CN, IR, or AE")
        return normalized


class ChangeRoleRequest(BaseModel):
    role: Role


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- Email OTP (2FA) flow ---

class OtpRequiredResponse(BaseModel):
    """Returned by /auth/register and /auth/login instead of a token —
    the frontend must now collect the code and call /auth/verify-otp."""
    otp_required: bool = True
    otp_token: str                 # opaque, short-lived — send back with the code
    email: EmailStr                # for showing "code sent to x@y.com"
    expires_in_minutes: int
    message: str


class VerifyOtpRequest(BaseModel):
    otp_token: str
    code: str = Field(min_length=4, max_length=8)


class ResendOtpRequest(BaseModel):
    otp_token: str


# --- Password reset flow ---

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=6, max_length=128)
