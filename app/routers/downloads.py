from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
from fastapi.responses import FileResponse
import tempfile

from app.services.patch_engine import apply_patch

# ✅ Para el flujo checkout/order_id
from app.routers.orders import ORDERS_DB

router = APIRouter(prefix="/download", tags=["download"])


# -------------------------------------------------------------------
# 1) NUEVO: Descarga por order_id (lo que tu checkout está llamando)
#    GET /download/<order_id>
# -------------------------------------------------------------------
@router.get("/{order_id}")
def download_by_order(order_id: str):
    o = ORDERS_DB.get(order_id)
    if not o:
        raise HTTPException(status_code=404, detail="order_id not found")

    if not o.get("download_ready"):
        raise HTTPException(status_code=403, detail="download not ready")

    path = o.get("mod_file_path")
    if not path:
        raise HTTPException(status_code=404, detail="mod file not found")

    # Nombre bonito (si aún no integras EFX en orders.py, lo hacemos acá)
    family = o.get("family") or "ECU"
    patch_id = o.get("patch_option_id") or "patch"
    filename = f"EFX_{family}_{patch_id}.mod.bin"

    return FileResponse(
        path,
        filename=filename,
        media_type="application/octet-stream"
    )


# -------------------------------------------------------------------
# 2) Tu endpoint original (lo dejo intacto)
#    POST /download/<ecu_type>/<patch_id> con upload de BIN stock
# -------------------------------------------------------------------
@router.post("/{ecu_type}/{patch_id}")
async def download_mod(
    ecu_type: str,
    patch_id: str,
    stock: UploadFile = File(...)
):
    stock_bytes = await stock.read()
    patch_dir = Path("app/data/patches") / ecu_type / patch_id

    if not patch_dir.exists():
        raise HTTPException(status_code=404, detail="Parche no existe")

    try:
        mod_bytes = apply_patch(stock_bytes, patch_dir)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mod.bin")
    tmp.write(mod_bytes)
    tmp.close()

    return FileResponse(
        tmp.name,
        filename=f"EFX_{patch_id}.mod.bin",
        media_type="application/octet-stream"
    )
