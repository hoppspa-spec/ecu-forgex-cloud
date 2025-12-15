from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Optional
import zlib

router = APIRouter(tags=["public"])

@router.get("/ping")
def ping():
    return {"ok": True}

def _latin1(s: bytes) -> str:
    try:
        return s.decode("latin-1", errors="ignore")
    except Exception:
        return ""

# Detector súper simple por patrones (sirve para la demo/EDC17C81)
ECU_KEYS = [
    "EDC17C81","EDC17","MD1","DCM","SID",
    "MED17.5","MED17","MEVD","MG1","ME7"
]

@router.post("/analyze_bin")
async def analyze_bin(bin_file: UploadFile = File(...)):
    if not bin_file:
        raise HTTPException(status_code=400, detail="bin_file requerido")

    data = await bin_file.read()
    size = len(data)
    if size == 0:
        raise HTTPException(status_code=400, detail="Archivo vacío")

    # CVN estilo CRC32 (mismo formato que usas en el front)
    cvn = f"{zlib.crc32(data) & 0xffffffff:08X}"

    # detección muy básica por texto
    text = _latin1(data).upper()
    ecu_type: Optional[str] = None
    for k in ECU_KEYS:
        if k in text:
            ecu_type = k
            break

    # (Opcional) PN/software: puedes mejorar esto más adelante
    ecu_part_number = None

    return {
        "analysis_id": f"local-{size}",
        "filename": bin_file.filename,
        "bin_size": size,
        "ecu_type": ecu_type or "Desconocida",
        "ecu_part_number": ecu_part_number,
        "cvn": cvn,
    }
