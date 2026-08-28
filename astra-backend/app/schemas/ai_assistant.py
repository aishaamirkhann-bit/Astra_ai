from pydantic import BaseModel
from app.schemas.product import ProductOut


class AiAssistantSuggestion(BaseModel):
    message: str                 # "Yeh product aapke liye best match hai:"
    product: ProductOut
    fits_budget: bool
    verified_seller: bool


class AddToCartRequest(BaseModel):
    product_slug: str
    quantity: int = 1
