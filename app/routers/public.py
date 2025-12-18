# app/routers/public.py
from fastapi import APIRouter, UploadFile, File, HTTPException
import zlib

router = APIRouter(prefix="", tags=["public"])

# memoria demo: analysis_id -> bytes
ANALYSIS_DB = {}

from pathlib import Path
import json

def normalize_ecu_family(ecu: str) -> str:
    if not ecu:
        return ""
    e = ecu.strip().upper()

    # corta por separadores típicos
    for sep in (" ", "-", "_"):
        if sep in e:
            e = e.split(sep, 1)[0]

    # familias por prefijo
    if e.startswith("EDC17"):
        return "EDC17"
    if e.startswith("MED17"):
        return "MED17"
    if e.startswith("MD1"):
        return "MD1"
    if e.startswith("MG1"):
        return "MG1"
    if e.startswith("MEVD"):
        return "MEVD"
    if e.startswith("DENSO"):
        return "DENSO"
    if e.startswith("SID"):
        return "SIEMENS_SID"
    if e.startswith("DCM"):
        return "CONTINENTAL_DCM"
    if e.startswith("DELPHI"):
        return "DELPHI"

    # fallback seguro
    return e[:6]


def ecu_matches(ecu_detected: str, compatible_list: list) -> bool:
    if not ecu_detected or not compatible_list:
        return False

    d = str(ecu_detected).strip().upper()
    fam_d = normalize_ecu_family(d)

    for c in compatible_list:
        if not c:
            continue
        cc = str(c).strip().upper()
        fam_c = normalize_ecu_family(cc)

        # match exacto
        if d == cc:
            return True
        # match por familia (EDC17C81 vs EDC17)
        if fam_d and fam_c and fam_d == fam_c:
            return True
        # match por substring (por si guardas variantes)
        if cc in d or d in cc:
            return True

    return False


def load_global_config() -> dict:
    # ajusta la ruta si tu global.json vive en otro lado
    path = Path("static") / "global.json"
    if not path.exists():
        path = Path("global.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

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

