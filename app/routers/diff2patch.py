from fastapi import APIRouter, UploadFile, File, Form
from pathlib import Path
from app.services.patch_engine import create_patch

router = APIRouter(prefix="/admin", tags=["diff2patch"])

@router.post("/diff2patch")
async def diff2patch(
    ecu_type: str = Form(...),
    patch_id: str = Form(...),
    stock: UploadFile = File(...),
    mod: UploadFile = File(...)
):
    stock_bytes = await stock.read()
    mod_bytes   = await mod.read()

    base_dir = Path("app/data/patches") / ecu_type / patch_id
    meta = create_patch(stock_bytes, mod_bytes, base_dir)

    return {
        "status": "ok",
        "ecu": ecu_type,
        "patch": patch_id,
        "meta": meta
    }
