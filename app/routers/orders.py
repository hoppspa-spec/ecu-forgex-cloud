# app/routers/orders.py
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
import uuid
from datetime import datetime

router = APIRouter(prefix="/orders", tags=["orders"])

class OrderCreate(BaseModel):
    analysis_id: str
    patch_option_id: str

# ---- STORAGE DEMO (en memoria) ----
ORDERS_DB = {}

def _require_token(authorization: str | None):
    # demo: basta con que exista algo como "Bearer xxx"
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    return authorization.split(" ", 1)[1].strip()

@router.post("")
def create_order(data: OrderCreate, authorization: str | None = Header(default=None)):
    token = _require_token(authorization)

    order_id = str(uuid.uuid4())
    order = {
        "id": order_id,
        "analysis_id": data.analysis_id,
        "patch_option_id": data.patch_option_id,
        "status": "pending_payment",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "download_ready": False,
        "token": token,  # 👈 para "mine" demo
    }
    ORDERS_DB[order_id] = order
    return {
        **order,
        "checkout_url": f"/static/checkout.html?order_id={order_id}",
    }

@router.get("/mine")
def my_orders(authorization: str | None = Header(default=None)):
    token = _require_token(authorization)
    orders = [o for o in ORDERS_DB.values() if o.get("token") == token]
    return {"orders": orders}

@router.get("/{order_id}")
def get_order(order_id: str, authorization: str | None = Header(default=None)):
    token = _require_token(authorization)
    o = ORDERS_DB.get(order_id)
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    if o.get("token") != token:
        raise HTTPException(status_code=403, detail="Forbidden")
    return o

@router.post("/{order_id}/confirm_payment")
def confirm_payment(order_id: str, authorization: str | None = Header(default=None)):
    token = _require_token(authorization)
    o = ORDERS_DB.get(order_id)
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    if o.get("token") != token:
        raise HTTPException(status_code=403, detail="Forbidden")

    o["status"] = "done"
    o["download_ready"] = True

    return {
        "ok": True,
        "order_id": order_id,
        "download_url": f"/download/{order_id}"
    }

@router.get("/{order_id}/download")
def download_link(order_id: str, authorization: str | None = Header(default=None)):
    token = _require_token(authorization)
    o = ORDERS_DB.get(order_id)
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    if o.get("token") != token:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not o.get("download_ready"):
        raise HTTPException(status_code=409, detail="Not ready yet")
    # redirige al router /download/{id}
    return {"url": f"/download/{order_id}"}
