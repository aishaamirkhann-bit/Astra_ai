from typing import Optional
from pydantic import BaseModel


class PipelineNodeOut(BaseModel):
    key: str
    label: str
    status: str          # "done" | "active" | "queued"
    latency_display: str  # "8ms" | "waiting" | "queued"
    log: str


class PipelineStateOut(BaseModel):
    order_ref: Optional[str] = None
    nodes: list[PipelineNodeOut]
    active_index: int
    current_verdict_label: str   # "Waiting on Approval"
    is_live: bool = True
