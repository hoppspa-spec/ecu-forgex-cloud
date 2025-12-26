from fastapi import APIRouter, HTTPException
from app.services.storage import load_order

router = APIRouter(prefix="/public", tags=["public"])

@router.get("/order/{order_id}")
def public_get_order(order_id: str):
    o = load_order(order_id)
    if not o:
        raise HTTPException(status_code=404, detail="order_id not found")

    # Público: devuelve solo lo necesario
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
        "sourceFileName": o.get("sourceFileName"),
        "sourceFileBytes": o.get("sourceFileBytes"),
        "detectedEcu": o.get("detectedEcu"),

        "vehicle": o.get("vehicle"),

        "checkout_url": o.get("checkout_url"),
        "download_url": f"/download/{order_id}" if o.get("download_ready") else None,
        "availablePatches": o.get("availablePatches") or [],
    }
