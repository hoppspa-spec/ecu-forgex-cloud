# app/routers/checkout_public.py
from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request

from app.services.storage import save_order, load_order  # ✅ mismo storage que orders.py

router = APIRouter(prefix="/public", tags=["public-checkout"])

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://ecu-forgex-cloud.onrender.com")

# precios base (USD)
PRICE = {
    "REV_LIMITER": 49,
    "DPF_OFF": 99,
    "EGR_OFF": 79,
    "CAT_OFF": 79,
    "ADBLUE_OFF": 89,
    "TOP_SPEED_OFF": 49,
    "DTC_OFF": 39,
}


def calc_total_usd(patches: List[str]) -> int:
    total = 0
    for p in patches:
        total += int(PRICE.get(str(p).strip(), 0))
    return total


def pick_customer_name(customer: Dict[str, Any]) -> str:
    # Wix te manda full_name + company, pero tu V1 pedía name
    name = (customer.get("full_name") or customer.get("name") or "").strip()
    if name:
        return name
    # fallback: si no hay nombre, usar company
    return (customer.get("company") or "").strip()


@router.post("/checkout")
async def public_checkout(req: Request):
    """
    Payload esperado desde Wix:
    {
      customer: {...},            # full_name, company, email, phone, address, comuna, country
      vehicle: {...},             # brand, model, serie, year, fuel, fuelDb, ecu
      selected_patches: [...],    # o patches: [...]
      currency: "USD",
      meta: {...}
    }
    """
    body = await req.json()

    customer = body.get("customer") or {}
    vehicle = body.get("vehicle") or {}
    patches = body.get("selected_patches") or body.get("patches") or []

    # -------- validar customer --------
    email = (customer.get("email") or "").strip()
    name = pick_customer_name(customer)

    if not email:
        raise HTTPException(status_code=400, detail="Missing customer.email")
    if not name:
        raise HTTPException(status_code=400, detail="Missing customer.full_name (or name)")

    # -------- validar patches --------
    if not isinstance(patches, list) or len(patches) == 0:
        raise HTTPException(status_code=400, detail="No patches selected")

    patches = [str(p).strip() for p in patches if str(p).strip()]
    if not patches:
        raise HTTPException(status_code=400, detail="No patches selected")

    total_usd = calc_total_usd(patches)
    if total_usd <= 0:
        raise HTTPException(status_code=400, detail="Invalid total (prices not found)")

    # -------- crear orden compatible con checkout.html / orders.py --------
    order_id = str(uuid.uuid4())

    order = {
        "id": order_id,
        "created_at": datetime.utcnow().isoformat(),

        # ✅ sin auth todavía: dejamos owner_email igual para trazabilidad
        "owner_email": email,

        # lo que viene desde Wix
        "customer": {
            **customer,
            "name": name,
        },
        "vehicle": vehicle,
        "selected_patches": patches,

        # precio
        "currency": "USD",
        "price_usd": float(total_usd),

        # estado inicial
        "status": "pending_payment",
        "paid": False,
        "download_ready": False,
        "download_url": None,

        # checkout (absoluto, para que Wix redirija sin dudas)
        "checkout_url": f"{PUBLIC_BASE_URL}/static/checkout.html?order_id={order_id}",

        # meta opcional
        "meta": body.get("meta") or {},
    }

    # ✅ persistir en el MISMO storage que orders.py
    save_order(order_id, order)

    return {
        "order_id": order_id,
        "checkout_url": order["checkout_url"],
        "total_usd": total_usd,
        "currency": "USD",
    }


@router.get("/order/{order_id}")
def public_order(order_id: str):
    o = load_order(order_id)
    if not o:
        raise HTTPException(status_code=404, detail="not_found")

    # ✅ respuesta pública mínima (lo que necesita analyze/checkout)
    return {
        "id": o.get("id"),
        "status": o.get("status"),
        "paid": o.get("paid"),
        "download_ready": o.get("download_ready"),
        "download_url": o.get("download_url"),
        "checkout_url": o.get("checkout_url"),
        "price_usd": o.get("price_usd"),
        "currency": o.get("currency", "USD"),
        "selected_patches": o.get("selected_patches") or o.get("patches") or [],
        "vehicle": o.get("vehicle") or {},
        "customer_email": (o.get("customer") or {}).get("email") or o.get("owner_email"),
        "created_at": o.get("created_at"),
    }


@router.post("/demo/confirm_payment/{order_id}")
def public_confirm_payment_demo(order_id: str):
    o = load_order(order_id)
    if not o:
        raise HTTPException(status_code=404, detail="not_found")

    # ✅ DEMO: pagado + descarga lista
    o["status"] = "paid"
    o["paid"] = True
    o["download_ready"] = True
    o["download_url"] = f"/download/{order_id}"

    save_order(order_id, o)

    return {"ok": True, "order_id": order_id, "download_url": o["download_url"]}
