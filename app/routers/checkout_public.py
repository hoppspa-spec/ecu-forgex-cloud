from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
import os, time, random
from typing import List, Dict, Any

router = APIRouter(prefix="/public", tags=["public-checkout"])

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://ecu-forgex-cloud.onrender.com")

# ====== STORE SIMPLE (V1) ======
ORDERS: Dict[str, Dict[str, Any]] = {}

PRICE = {
    "REV_LIMITER": 49,
    "DPF_OFF": 99,
    "EGR_OFF": 79,
    "CAT_OFF": 79,
    "ADBLUE_OFF": 89,
    "TOP_SPEED_OFF": 49,
    "DTC_OFF": 39,
}

def uid(prefix="ORD"):
    return f"{prefix}_{int(time.time())}_{random.randint(1000,9999)}"

def calc_total(patches: List[str]) -> int:
    return sum(PRICE.get(p, 0) for p in patches)

@router.post("/checkout")
async def public_checkout(req: Request):
    body = await req.json()
    customer = body.get("customer") or {}
    vehicle = body.get("vehicle") or {}
    patches = body.get("patches") or []

    if not customer.get("email") or not customer.get("name"):
        raise HTTPException(status_code=400, detail="Missing customer name/email")
    if not isinstance(patches, list) or len(patches) == 0:
        raise HTTPException(status_code=400, detail="No patches selected")

    total = calc_total(patches)
    if total <= 0:
        raise HTTPException(status_code=400, detail="Invalid total")

    order_id = uid()
    ORDERS[order_id] = {
        "id": order_id,
        "status": "created",
        "paid": False,
        "download_ready": False,
        "download_url": None,
        "total_usd": total,
        "patches": patches,
        "customer": customer,
        "vehicle": vehicle,
        "created_at": time.time(),
    }

    # V1: como aún no estamos integrando PayPal real acá,
    # devolvemos checkout_url apuntando a tu static/checkout.html
    checkout_url = f"{PUBLIC_BASE_URL}/static/checkout.html?order_id={order_id}"
    ORDERS[order_id]["checkout_url"] = checkout_url

    return {"order_id": order_id, "checkout_url": checkout_url}

@router.get("/order/{order_id}")
async def public_order(order_id: str):
    o = ORDERS.get(order_id)
    if not o:
        raise HTTPException(status_code=404, detail="not_found")
    return {
        "id": o["id"],
        "status": o["status"],
        "paid": o["paid"],
        "download_ready": o["download_ready"],
        "download_url": o["download_url"],
        "checkout_url": o.get("checkout_url"),
        "patches": o["patches"],
        "total_usd": o["total_usd"],
    }

@router.post("/demo/confirm_payment/{order_id}")
async def demo_confirm_payment(order_id: str):
    o = ORDERS.get(order_id)
    if not o:
        raise HTTPException(status_code=404, detail="not_found")

    # DEMO: marcar como pagado + “descarga lista”
    o["paid"] = True
    o["status"] = "paid"
    o["download_ready"] = True

    # Si ya tienes endpoint real /download/{order_id}, ponlo aquí:
    o["download_url"] = f"{PUBLIC_BASE_URL}/download/{order_id}"

    return {"ok": True, "download_url": o["download_url"]}
