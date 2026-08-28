from typing import Optional
from pydantic import BaseModel, ConfigDict


class ProductOut(BaseModel):
    slug: str
    name: str
    price_display: str        # "Rs. 314,999" — formatted for direct rendering
    price: float               # raw number, for calculations on frontend if needed
    rating: float
    tag: Optional[str] = None
    fit: str                   # "Fits your budget" | "Stretch (Manageable)" | "Over budget"
    seller: str
    trust: int
    category: str
    image: Optional[str] = None
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
