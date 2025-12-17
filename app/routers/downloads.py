from fastapi import APIRouter
from fastapi.responses import FileResponse
import tempfile

router = APIRouter(prefix="/download", tags=["download"])

@router.get("/{order_id}")
def download_bin(order_id: str):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mod.bin")
    tmp.write(f"ECU FORGE X - BIN MOD DEMO\nORDER={order_id}\n".encode("utf-8"))
    tmp.close()

    return FileResponse(
        tmp.name,
        filename=f"ecu_forgex_{order_id}.mod.bin",
        media_type="application/octet-stream"
    )
