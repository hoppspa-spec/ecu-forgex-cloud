# app/routers/public.py
from fastapi import APIRouter, UploadFile, File, HTTPException
import zlib

router = APIRouter(prefix="", tags=["public"])

# memoria demo: analysis_id -> bytes
ANALYSIS_DB = {}

@router.post("/analyze_bin")
async def analyze_bin(bin_file: UploadFile = File(...)):
    data = await bin_file.read()
    size = len(data)
    crc = zlib.crc32(data) & 0xFFFFFFFF

    ecu_type = "EDC17C81" if size > 2_000_000 else "UNKNOWN"
    analysis_id = f"demo-{crc:08X}-{size}"

    ANALYSIS_DB[analysis_id] = {
        "bytes": data,
        "filename": bin_file.filename,
        "ecu_type": ecu_type,
        "bin_size": size,
        "cvn_crc32": f"{crc:08X}"
    }

    return {
        "analysis_id": analysis_id,
        "filename": bin_file.filename,
        "bin_size": size,
        "cvn_crc32": f"{crc:08X}",
        "ecu_type": ecu_type,
        "ecu_part_number": None
    }
