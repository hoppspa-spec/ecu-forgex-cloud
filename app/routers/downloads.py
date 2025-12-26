# app/routers/download.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.storage import load_order

router = APIRouter(prefix="/download", tags=["download"])


@router.get("/{order_id}")
def download_by_order(order_id: str):
    """
    Descarga el archivo MOD final asociado a un order_id
    (flujo post-checkout).
    """
    o = load_order(order_id)
    if not o:
        raise HTTPException(status_code=404, detail="order_id not found")

    if not o.get("paid"):
        raise HTTPException(status_code=403, detail="order not paid")

    if not o.get("download_ready"):
        raise HTTPException(status_code=403, detail="download not ready")

    paths = o.get("paths") or {}
    mod_path = paths.get("mod_file_path")

    if not mod_path:
        raise HTTPException(status_code=404, detail="mod file not found")

    # Nombre bonito del archivo
    family = o.get("family") or o.get("detectedEcu") or "ECU"
    patch_id = o.get("patch_option_id") or "patch"

    filename = f"EFX_{family}_{patch_id}.mod.bin"

    return FileResponse(
        path=mod_path,
        filename=filename,
        media_type="application/octet-stream",
    )
