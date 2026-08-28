from typing import Literal
from pydantic import BaseModel


class ApprovalStatusOut(BaseModel):
    order_ref: str
    status: Literal["pending", "approved", "cancelled"]
    seconds_left: int
    window_seconds: int
    prompt_text: str = "Order ready hai, kya final checkout karain?"


class ApprovalActionRequest(BaseModel):
    order_ref: str


class ApprovalActionResponse(BaseModel):
    order_ref: str
    status: Literal["approved", "cancelled"]
    message: str
