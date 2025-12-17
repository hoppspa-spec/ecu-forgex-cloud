from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from app.routers.orders import ORDERS_DB

router = APIRouter(prefix="/download", tags=["download"])

@router.get("/{order_id}")
def download_bin(order_id: str):
    o = ORDERS_DB.get(order_id)
    if not o or not o.get("download_ready"):
        raise HTTPException(status_code=404, detail="Download not ready")

    return FileResponse(
        o["mod_file_path"],
        filename=f"ecu_forgex_{order_id}.mod.bin",
        media_type="application/octet-stream"
    )
