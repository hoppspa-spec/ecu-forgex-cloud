# app/routers/public.py
from fastapi import APIRouter, UploadFile, File
import zlib

router = APIRouter(tags=["public"])

@router.post("/analyze_bin")
async def analyze_bin(bin_file: UploadFile = File(...)):
    data = await bin_file.read()

    size = len(data)
    crc = zlib.crc32(data) & 0xFFFFFFFF

    # demo: detecta familia por tamaño
    ecu_type = "EDC17C81" if size > 2_000_000 else "UNKNOWN"

    return {
        "analysis_id": "demo-analysis-001",
        "filename": bin_file.filename,
        "bin_size": size,
        "cvn_crc32": f"{crc:08X}",
        "ecu_type": ecu_type,
        "ecu_part_number": None
    }
