# app/routers/downloads.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os
import tempfile

router = APIRouter(prefix="/download", tags=["download"])

@router.get("/{order_id}")
def download_bin(order_id: str):
    # DEMO: genera un BIN falso modificado
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mod.bin")
    tmp.write(b"ECU FORGE X — BIN MOD DEMO\n")
    tmp.close()

    return FileResponse(
        tmp.name,
        filename=f"ecu_forgex_{order_id}.mod.bin",
        media_type="application/octet-stream"
    )
