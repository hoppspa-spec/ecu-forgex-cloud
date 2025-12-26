# app/routers/public_orders.py
from fastapi import APIRouter, HTTPException
from app.routers.orders import ORDERS_DB  # 👈 in-memory DB actual

router = APIRouter(prefix="/public", tags=["public"])

@router.get("/order/{order_id}")
def public_get_order(order_id: str):
    o = ORDERS_DB.get(order_id)
    if not o:
        raise HTTPException(status_code=404, detail="order_id not found")

    # ⚠️ Público: devuelve solo lo necesario (no emails, no rutas internas)
    return {
        "id": o.get("id"),
        "created_at": o.get("created_at"),
        "status": o.get("status"),
        "paid": o.get("paid"),
        "download_ready": o.get("download_ready"),
        "family": o.get("family"),
        "engine": o.get("engine"),
        "patch_option_id": o.get("patch_option_id"),
        "patch_label": o.get("patch_label"),
        "price_usd": o.get("price_usd"),
        "original_filename": o.get("original_filename"),

        # si quieres mostrar el checkout link en Wix:
        "checkout_url": o.get("checkout_url"),

        # si está listo, muestra download:
        "download_url": f"/download/{order_id}" if o.get("download_ready") else None,
    }
