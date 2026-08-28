from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class PipelineRun(Base):
    """One row per checkout intent going through the ASTRA Decision Pipeline."""
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    current_stage = Column(String(40), default="intent")   # matches PIPELINE_STAGES keys on frontend
    verdict = Column(String(40), default="processing")     # processing | approve | reject | waiting_approval
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    stages = relationship("PipelineStageLog", back_populates="run")


class PipelineStageLog(Base):
    """Per-stage timing + message, powers the node-detail popover on PipelineBar."""
    __tablename__ = "pipeline_stage_logs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("pipeline_runs.id"), nullable=False)
    stage_key = Column(String(40), nullable=False)   # intent | finance | contradiction | trust | approval | checkout
    label = Column(String(80), nullable=False)
    latency_ms = Column(Integer, nullable=True)      # null while stage is waiting/queued
    message = Column(String(300), nullable=False)
    completed_at = Column(DateTime(timezone=True), server_default=func.now())

    run = relationship("PipelineRun", back_populates="stages")


class AuditLog(Base):
    """Every consent/finance/trust decision, for the audit trail (compliance requirement)."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    event_ref = Column(String(30), unique=True, nullable=False)   # "EVT-4471"
    event_type = Column(String(60), nullable=False)               # "consent.evaluate", "human.approval" ...
    endpoint = Column(String(120), nullable=False)
    verdict = Column(String(30), nullable=False)
    actor = Column(String(80), nullable=False)                    # "orchestrator-agent" | "user:aisha.k" | ...
    created_at = Column(DateTime(timezone=True), server_default=func.now())
