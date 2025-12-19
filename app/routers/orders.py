# app/routers/orders.py
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
import uuid, tempfile
from datetime import datetime

from app.services.patcher import apply_patch
from app.routers.public import ANALYSIS_DB, load_global_config, ecu_matches
from app.routers.auth import get_current_user  # ✅ usamos el auth real

router = APIRouter(prefix="/orders", tags=["orders"])

class OrderCreate(BaseModel):
    analysis_id: str
    patch_option_id: str

ORDERS_DB = {}

def find_patch_for_family(family: str, engine: str, patch_id: str) -> dict | None:
    cfg = load_global_config()
    patches = cfg.get("patches", [])

    fam = (family or "").strip()
    eng = (engine or "auto").strip().lower()
    if eng == "auto":
        eng = "diesel"  # demo

    pid = (patch_id or "").strip()

    for p in patches:
        if p.get("id") != pid:
            continue

        engines = p.get("engines")
        if isinstance(engines, list) and eng:
            if eng not in [str(e).lower() for e in engines]:
                continue

        if not ecu_matches(fam, p.get("compatible_ecu", [])):
            continue

        return p

    return None

@router.post("")
def create_order(data: OrderCreate, u: dict = Depends(get_current_user)):
    a = ANALYSIS_DB.get(data.analysis_id)
    if not a:
        raise HTTPException(status_code=404, detail="analysis_id not found")

    family = a.get("ecu_type") or "UNKNOWN"
    engine = a.get("engine") or "auto"

    patch = find_patch_for_family(family, engine, data.patch_option_id)
    if not patch:
        raise HTTPException(status_code=404, detail="patch_option_id not found for this family")

    size = int(a.get("bin_size") or 0)
    rules = patch.get("rules") or {}
    if rules.get("min_size") and size < int(rules["min_size"]):
        raise HTTPException(status_code=400, detail="BIN too small for this patch")
    if rules.get("max_size") and size > int(rules["max_size"]):
        raise HTTPException(status_code=400, detail="BIN too large for this patch")

    price_usd = (patch.get("price") or {}).get("USD")
    files = patch.get("files") or {}
    yml_path = files.get("yml")
    diff_path = files.get("diff")

    mod_bytes = apply_patch(a["bytes"], patch)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mod.bin")
    tmp.write(mod_bytes)
    tmp.close()

    order_id = str(uuid.uuid4())
    order = {
        "id": order_id,
        "created_at": datetime.utcnow().isoformat(),
        "owner_email": u["email"],  # ✅ dueño
        "analysis_id": data.analysis_id,
        "family": family,
        "engine": engine,
        "patch_option_id": data.patch_option_id,
        "patch_label": patch.get("label"),
        "price_usd": price_usd,
        "yml_path": yml_path,
        "diff_path": diff_path,
        "status": "pending_payment",   # ✅ ahora sí: no queda listo gratis
        "paid": False,
        "download_ready": False,
        "mod_file_path": tmp.name,
        "original_filename": a.get("filename"),
        "checkout_url": f"/static/checkout.html?order_id={order_id}",
    }

    ORDERS_DB[order_id] = order
    return order

@router.get("/mine")
def my_orders(u: dict = Depends(get_current_user)):
    mine = [o for o in ORDERS_DB.values() if o.get("owner_email") == u["email"]]
    mine.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return {"orders": mine}

@router.get("/{order_id}")
def get_order(order_id: str, u: dict = Depends(get_current_user)):
    o = ORDERS_DB.get(order_id)
    if not o:
        raise HTTPException(status_code=404, detail="order_id not found")

    # ✅ dueño o admin
    if o.get("owner_email") != u["email"] and u.get("role") != "admin":
        raise HTTPException(status_code=403, detail="forbidden")

    return o

@router.post("/{order_id}/confirm_payment")
def confirm_payment_demo(order_id: str, u: dict = Depends(get_current_user)):
    o = ORDERS_DB.get(order_id)
    if not o:
        raise HTTPException(status_code=404, detail="order_id not found")

    if o.get("owner_email") != u["email"] and u.get("role") != "admin":
        raise HTTPException(status_code=403, detail="forbidden")

    # demo: marcar pagado
    o["status"] = "paid"
    o["paid"] = True
    o["download_ready"] = True

    return {
        "ok": True,
        "order_id": order_id,
        "status": o["status"],
        "download_url": f"/download/{order_id}",
    }
