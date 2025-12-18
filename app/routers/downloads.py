from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
from fastapi.responses import FileResponse
import tempfile

from app.services.patch_engine import apply_patch

router = APIRouter(prefix="/download", tags=["download"])

@router.post("/{ecu_type}/{patch_id}")
async def download_mod(
    ecu_type: str,
    patch_id: str,
    stock: UploadFile = File(...)
):
    stock_bytes = await stock.read()
    patch_dir = Path("app/data/patches") / ecu_type / patch_id

    if not patch_dir.exists():
        raise HTTPException(404, "Parche no existe")

    try:
        mod_bytes = apply_patch(stock_bytes, patch_dir)
    except ValueError as e:
        raise HTTPException(400, str(e))

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mod.bin")
    tmp.write(mod_bytes)
    tmp.close()

    return FileResponse(
        tmp.name,
        filename=f"{patch_id}.mod.bin",
        media_type="application/octet-stream"
    )
