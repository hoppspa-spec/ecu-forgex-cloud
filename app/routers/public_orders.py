# app/routers/public_orders.py
from fastapi import APIRouter, HTTPException
from app.routers.orders import ORDERS_DB  # reutilizamos en memoria

router = APIRouter(prefix="/public", tags=["public"])

@router.get("/order/{order_id}")
def public_get_order(order_id: str):
    o = ORDERS_DB.get(order_id)
    if not o:
        raise HTTPException(status_code=404, detail="order_id not found")

    # ✅ solo devolvemos campos seguros (sin owner_email, mod_file_path, etc.)
    return {
        "id": o.get("id"),
        "status": o.get("status"),
        "paid": o.get("paid"),
        "download_ready": o.get("download_ready"),
        "patch_label": o.get("patch_label"),
        "price_usd": o.get("price_usd"),
        "family": o.get("family"),
        "engine": o.get("engine"),
        "checkout_url": o.get("checkout_url"),
    }
