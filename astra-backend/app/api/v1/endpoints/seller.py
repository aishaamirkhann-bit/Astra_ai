import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.user import User
from app.services.audit import record_audit

router = APIRouter(prefix="/seller", tags=["Seller Dashboard"])


class InventoryInput(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=80)
    price: float = Field(gt=0)
    stock_count: int = Field(ge=0)
    description: str = Field(default="", max_length=2000)
    image_url: str = "/images/products/default-product.png"


class InventoryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=160)
    category: str | None = Field(default=None, min_length=2, max_length=80)
    price: float | None = Field(default=None, gt=0)
    stock_count: int | None = Field(default=None, ge=0)
    description: str | None = Field(default=None, max_length=2000)
    image_url: str | None = None


def _seller_slug(user: User) -> str:
    return re.sub(r"[^a-z0-9]+", "-", user.name.lower()).strip("-")


def _product_out(product: Product) -> dict:
    return {"id": product.id, "title": product.title, "category": product.category, "price": product.base_price, "stock_count": product.stock_count, "status": "in_stock" if product.stock_count else "out_of_stock", "image_url": product.image_url}


@router.get("/inventory")
def inventory(db: Session = Depends(get_db), seller: User = Depends(require_role("seller"))):
    products = db.query(Product).filter(Product.seller_name == seller.name).order_by(Product.title).all()
    return [_product_out(product) for product in products]


@router.post("/inventory", status_code=201)
def create_inventory(payload: InventoryInput, db: Session = Depends(get_db), seller: User = Depends(require_role("seller"))):
    base = re.sub(r"[^a-z0-9]+", "-", payload.title.lower()).strip("-")
    product_id, suffix = base, 2
    while db.get(Product, product_id):
        product_id, suffix = f"{base}-{suffix}", suffix + 1
    product = Product(
        id=product_id, title=payload.title, category=payload.category, base_price=payload.price,
        stock_count=payload.stock_count, description=payload.description or payload.title,
        image_url=payload.image_url, seller_name=seller.name, seller_id=_seller_slug(seller),
        rating=0, total_reviews=0, is_verified_seller=True, semantic_tags="seller listing,verified seller",
        fit="Seller managed", trust=85, search_terms=f"{payload.title},{payload.category}",
    )
    db.add(product); db.commit(); db.refresh(product)
    return _product_out(product)


@router.patch("/inventory/{product_id}")
def update_inventory(product_id: str, payload: InventoryUpdate, db: Session = Depends(get_db), seller: User = Depends(require_role("seller"))):
    product = db.query(Product).filter(Product.id == product_id, Product.seller_name == seller.name).first()
    if not product: raise HTTPException(status_code=404, detail="Inventory item not found")
    values = payload.model_dump(exclude_unset=True)
    if "price" in values: product.base_price = values.pop("price")
    for key, value in values.items(): setattr(product, key, value)
    db.commit(); db.refresh(product)
    return _product_out(product)


@router.delete("/inventory/{product_id}", status_code=204)
def delete_inventory(product_id: str, db: Session = Depends(get_db), seller: User = Depends(require_role("seller"))):
    product = db.query(Product).filter(Product.id == product_id, Product.seller_name == seller.name).first()
    if not product: raise HTTPException(status_code=404, detail="Inventory item not found")
    if db.query(Order).filter(Order.product_id == product.id).first():
        raise HTTPException(status_code=409, detail="Products with order history cannot be deleted; set stock to zero")
    db.delete(product); db.commit()
    return Response(status_code=204)


@router.get("/orders")
def seller_orders(db: Session = Depends(get_db), seller: User = Depends(require_role("seller"))):
    orders = db.query(Order).join(Product).filter(Product.seller_name == seller.name).order_by(Order.created_at.desc()).all()
    return [{"order_ref": o.order_ref, "product_name": o.product.title, "quantity": o.quantity, "total": o.price, "order_status": o.status.value, "escrow_status": "LOCKED" if o.escrow_status == "HELD" else o.escrow_status, "placed_at": o.created_at} for o in orders]


@router.post("/orders/{order_ref}/dispatch")
def dispatch(order_ref: str, db: Session = Depends(get_db), seller: User = Depends(require_role("seller"))):
    order = db.query(Order).join(Product).filter(Order.order_ref == order_ref, Product.seller_name == seller.name).first()
    if not order: raise HTTPException(status_code=404, detail="Seller order not found")
    if order.escrow_status != "HELD" or order.status in {OrderStatus.CANCELLED, OrderStatus.DELIVERED}:
        raise HTTPException(status_code=409, detail="Order cannot be dispatched")
    order.status, order.shipped_at = OrderStatus.SHIPPED, datetime.now(timezone.utc)
    record_audit(db, event_type="seller.dispatch", endpoint=f"/api/v1/seller/orders/{order_ref}/dispatch", verdict="shipped", actor=f"seller:{seller.email}")
    db.commit()
    return {"order_ref": order_ref, "order_status": "shipped", "escrow_status": "LOCKED"}
