from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

from app.services.storage import load_order

router = APIRouter(prefix="/download", tags=["download"])

@router.get("/{order_id}")
def download_by_order(order_id: str):
    o = load_order(order_id)
    if not o:
        raise HTTPException(status_code=404, detail="order_id not found")

    if not o.get("download_ready"):
        raise HTTPException(status_code=403, detail="download not ready")

    path = o.get("mod_file_path")
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="mod file not found")

    family = o.get("family") or "ECU"
    patch_id = o.get("patch_option_id") or "patch"
    filename = f"EFX_{family}_{patch_id}.mod.bin"

    return FileResponse(
        path,
        filename=filename,
        media_type="application/octet-stream"
    )
