# app/routers/public_orders.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.storage import load_order

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/order/{order_id}")
def public_get_order(order_id: str):
    o = load_order(order_id)
    if not o:
        raise HTTPException(status_code=404, detail="order_id not found")

    # ✅ público sanitizado (nada de emails ni rutas internas)
    return {
        "id": o.get("id"),
        "created_at": o.get("created_at"),
        "status": o.get("status"),
        "paid": o.get("paid"),
        "download_ready": o.get("download_ready"),

        "vehicle": o.get("vehicle"),
        "detectedEcu": o.get("detectedEcu"),
        "sourceFileName": o.get("sourceFileName"),
        "sourceFileBytes": o.get("sourceFileBytes"),

        "availablePatches": o.get("availablePatches"),

        # si luego metes pagos:
        "checkout_url": o.get("checkout_url"),
        "download_url": o.get("download_url") if o.get("download_ready") else None,
    }
