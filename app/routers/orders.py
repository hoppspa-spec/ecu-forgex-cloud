# app/routers/orders.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import uuid

router = APIRouter(prefix="/orders", tags=["orders"])

# ---- MODELO ----
class OrderCreate(BaseModel):
    analysis_id: str
    patch_option_id: str

# ---- STORAGE DEMO (en memoria) ----
ORDERS_DB = {}

@router.post("")
def create_order(data: OrderCreate):
    order_id = str(uuid.uuid4())

    order = {
        "id": order_id,
        "analysis_id": data.analysis_id,
        "patch_option_id": data.patch_option_id,
        "status": "paid",  # 👈 demo: pagado al tiro
        "checkout_url": f"/static/checkout.html?order_id={order_id}"
    }

    ORDERS_DB[order_id] = order
    return order


@router.get("/{order_id}")
def get_order(order_id: str):
    order = ORDERS_DB.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
