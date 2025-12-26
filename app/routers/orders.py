# app/routers/orders.py
from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.services.patcher import apply_patch
from app.routers.public import ANALYSIS_DB, load_global_config, ecu_matches
from app.routers.auth import get_current_user

from app.services.storage import (
    order_dir, save_order, load_order
)

router = APIRouter(prefix="/orders", tags=["orders"])


class OrderCreate(BaseModel):
    analysis_id: str
    patch_option_id: str


def find_patch_for_family(family: str, engine: str, patch_id: str) -> dict | None:
    cfg = load_global_config()
    patches = cfg.get("patches", [])

    fam = (family or "").strip()
    eng = (engine or "auto").strip().lower()
    if eng == "auto":
        eng = "diesel"  # demo default

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

    # ✅ genera mod
    mod_bytes = apply_patch(a["bytes"], patch)

    order_id = str(uuid.uuid4())
    odir = order_dir(order_id)

    # ✅ persistimos el mod en el disk (no tempfile)
    mod_path = odir / "output.mod.bin"
    with open(mod_path, "wb") as f:
        f.write(mod_bytes)

    order = {
        "id": order_id,
        "created_at": datetime.utcnow().isoformat(),
        "owner_email": u["email"],

        "analysis_id": data.analysis_id,
        "family": family,
        "engine": engine,

        "patch_option_id": data.patch_option_id,
        "patch_label": patch.get("label"),
        "price_usd": price_usd,

        "status": "pending_payment",
        "paid": False,
        "download_ready": False,

        # ✅ paths internos (no exponer en public)
        "paths": {
            "mod_file_path": str(mod_path),
        },

        "original_filename": a.get("filename"),
        "checkout_url": f"/static/checkout.html?order_id={order_id}",
    }

    save_order(order_id, order)
    return order


@router.get("/mine")
def my_orders(u: dict = Depends(get_current_user)):
    all_orders = iter_orders()
    mine = [o for o in all_orders if o.get("owner_email") == u["email"]]
    mine.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return {"orders": mine}


@router.get("/{order_id}")
def get_order(order_id: str, u: dict = Depends(get_current_user)):
    o = load_order(order_id)
    if not o:
        raise HTTPException(status_code=404, detail="order_id not found")

    if o.get("owner_email") != u["email"] and u.get("role") != "admin":
        raise HTTPException(status_code=403, detail="forbidden")

    return o


@router.post("/{order_id}/confirm_payment")
def confirm_payment_demo(order_id: str, u: dict = Depends(get_current_user)):
    o = load_order(order_id)
    if not o:
        raise HTTPException(status_code=404, detail="order_id not found")

    if o.get("owner_email") != u["email"] and u.get("role") != "admin":
        raise HTTPException(status_code=403, detail="forbidden")

    o["status"] = "paid"
    o["paid"] = True
    o["download_ready"] = True
    o["download_url"] = f"/download/{order_id}"

    save_order(order_id, o)

    return {
        "ok": True,
        "order_id": order_id,
        "status": o["status"],
        "download_url": o["download_url"],
    }

