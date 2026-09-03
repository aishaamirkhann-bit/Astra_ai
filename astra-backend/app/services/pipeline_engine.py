"""
PipelineEngine
--------------
Builds the 6-node "ASTRA Decision Pipeline" state that PipelineBar.tsx renders.
Static node metadata mirrors PIPELINE_STAGES in the frontend's mockData.ts —
keep the `key`/`label` values in sync if you edit one side.
"""
from app.models.order import Order, OrderStatus
from app.schemas.pipeline import PipelineNodeOut, PipelineStateOut

PIPELINE_STAGES = [
    {"key": "intent", "label": "Intent Received", "latency": "8ms",
     "log": "Parsed voice/text intent → structured query."},
    {"key": "finance", "label": "Finance Rules", "latency": "42ms",
     "log": "Checked against budget cap and wallet balance."},
    {"key": "contradiction", "label": "Contradiction Check", "latency": "31ms",
     "log": "No conflicting prior commitments found."},
    {"key": "trust", "label": "Trust Engine", "latency": "68ms",
     "log": "Seller trust score computed."},
    {"key": "approval", "label": "Human Approval", "latency": "waiting",
     "log": "Awaiting your confirmation."},
    {"key": "checkout", "label": "Reversible Checkout", "latency": "queued",
     "log": "30s reversal window will open on approval."},
]


class PipelineEngine:
    @staticmethod
    def build_state(order: Order | None) -> PipelineStateOut:
        # Map order status -> which node is currently "active" (0-indexed)
        if order is None or order.status == OrderStatus.PENDING_APPROVAL:
            active_index = 4  # Human Approval
            verdict_label = "Waiting on Approval"
        elif order.status == OrderStatus.REVERSAL_WINDOW_OPEN:
            active_index = 5  # Reversible Checkout
            verdict_label = "Reversal Window Open"
        elif order.status == OrderStatus.CONFIRMED:
            active_index = 6
            verdict_label = "Confirmed — Ready for Dispatch"
        elif order.status == OrderStatus.SHIPPED:
            active_index = 6
            verdict_label = "Shipped"
        elif order.status == OrderStatus.DELIVERED:
            active_index = 6
            verdict_label = "Delivered"
        else:
            active_index = 5
            verdict_label = "Cancelled — Refund Started"

        nodes = []
        for i, stage in enumerate(PIPELINE_STAGES):
            if i < active_index:
                status = "done"
            elif i == active_index:
                status = "active"
            else:
                status = "queued"
            nodes.append(
                PipelineNodeOut(
                    key=stage["key"],
                    label=stage["label"],
                    status=status,
                    latency_display=stage["latency"],
                    log=stage["log"],
                )
            )

        return PipelineStateOut(
            order_ref=order.order_ref if order else None,
            nodes=nodes,
            active_index=min(active_index, len(PIPELINE_STAGES) - 1),
            current_verdict_label=verdict_label,
            is_live=True,
        )
