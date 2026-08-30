from pydantic import BaseModel

from app.schemas.product import ProductOut
from app.schemas.astra_check import AstraCheckOut
from app.schemas.ai_assistant import AiAssistantSuggestion
from app.schemas.approval import ApprovalStatusOut
from app.schemas.pipeline import PipelineStateOut
from app.schemas.goal import GoalsWalletRailOut
from app.schemas.user import UserOut


class HeroSuggestion(BaseModel):
    label: str
    href: str


class HomePageOut(BaseModel):
    """
    Ek single call jo poore Home page ko hydrate kar deta hai.
    Frontend chahe to individual endpoints bhi use kar sakta hai
    (products/, astra-check/, approval/ etc.) — yeh sirf pehli load
    ko fast banane ke liye hai (1 round-trip instead of 6).
    """
    hero_suggestions: list[HeroSuggestion]
    recommended_products: list[ProductOut]
    astra_check: AstraCheckOut | None
    ai_assistant: AiAssistantSuggestion | None
    approval: ApprovalStatusOut | None
    pipeline: PipelineStateOut
    goals_wallet: GoalsWalletRailOut
    unread_notifications: int
    user: UserOut
