import os, uuid, shutil, zipfile
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api", tags=["ingest"])

# ------- Storage simple (V1 en memoria) -------
ORDERS_DB: Dict[str, Dict[str, Any]] = {}

TMP_DIR = os.getenv("EFX_TMP", "/tmp/efx")
os.makedirs(TMP_DIR, exist_ok=True)

MIN_BYTES = 32 * 1024
MAX_BYTES = 64 * 1024 * 1024

ALLOWED_EXTS = {".bin", ".ori", ".mod", ".mpc", ".hex", ".s19", ".srec", ".e2p", ".eep", ".rom", ".frf", ".dat"}
IGNORE_EXTS  = {".txt", ".nfo", ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".xml", ".json", ".csv", ".ini", ".log"}

def _iter_files(root: str) -> List[str]:
    out = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            out.append(os.path.join(dirpath, fn))
    return out

def pick_ecu_file(extract_dir: str) -> Optional[str]:
    candidates: List[Tuple[int, int, str]] = []  # (score, size, path)
    for p in _iter_files(extract_dir):
        name = os.path.basename(p)
        ext = Path(name).suffix.lower()

        try:
            size = os.path.getsize(p)
        except OSError:
            continue
        if size <= 0:
            continue
        if ext in IGNORE_EXTS:
            continue

        score = 0
        if ext in ALLOWED_EXTS:
            score = 2
        elif ext == ".zip":
            score = -5
        else:
            score = 1

        low = name.lower()
        if any(k in low for k in ["readme", "info", "license", "metadata", "checksum", "md5", "sha", "project"]):
            score -= 2

        candidates.append((score, size, p))

    if not candidates:
        return None

    candidates.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return candidates[0][2]

def _looks_like_zip(path: str) -> bool:
    # ZIP magic bytes
    try:
        with open(path, "rb") as f:
            head = f.read(4)
        return head in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
    except Exception:
        return False

@router.post("/ingest-multipart")
async def ingest_multipart(
    file: UploadFile = File(...),
    brand: str = Form(""),
    model: str = Form(""),
    year: str = Form(""),
    engine: str = Form(""),
    ecu: str = Form("")
):
    order_id = str(uuid.uuid4())
    workdir = os.path.join(TMP_DIR, order_id)
    extract_dir = os.path.join(workdir, "extract")
    os.makedirs(extract_dir, exist_ok=True)

    # guardamos el archivo tal cual (sin depender del nombre)
    safe_name = os.path.basename(file.filename or "upload.bin")
    raw_path = os.path.join(workdir, safe_name)

    try:
        with open(raw_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
    except Exception as e:
        raise HTTPException(500, f"Failed to save upload: {e}")

    # ¿Es ZIP real? (por magic bytes, no por extensión)
    is_zip = _looks_like_zip(raw_path)

    ecu_file = raw_path
    if is_zip:
        try:
            with zipfile.ZipFile(raw_path, "r") as z:
                z.extractall(extract_dir)
        except zipfile.BadZipFile:
            raise HTTPException(400, "Invalid ZIP file")

        ecu_pick = pick_ecu_file(extract_dir)
        if not ecu_pick:
            raise HTTPException(400, "No ECU file found inside ZIP")
        ecu_file = ecu_pick

    size = os.path.getsize(ecu_file)
    if size < MIN_BYTES:
        raise HTTPException(400, f"ECU file too small: {size} bytes")
    if size > MAX_BYTES:
        raise HTTPException(400, f"ECU file too large: {size} bytes")

    detected_ecu = ecu or "UNKNOWN"

    # Parches demo (V1)
    available_patches = [
        {"id":"speed_limiter", "name":"Speed Limiter OFF", "desc":"Remove or raise speed limiter.", "price":49, "tag":"Popular"},
        {"id":"dtc_off", "name":"DTC OFF", "desc":"Deactivate selected DTCs.", "price":39, "tag":"Fast"},
        {"id":"dpf_off", "name":"DPF OFF (off-road)", "desc":"Disable DPF (off-road only).", "price":99, "tag":"Diesel"},
    ]

    # Guardamos order en memoria para que Wix lo lea con /public/order/{orderId}
    ORDERS_DB[order_id] = {
        "orderId": order_id,
        "detectedEcu": detected_ecu,
        "sourceFileName": os.path.basename(ecu_file),
        "sourceFileBytes": size,
        "isZip": bool(is_zip),
        "vehicle": {"brand": brand, "model": model, "year": year, "engine": engine, "ecu": ecu},
        "availablePatches": available_patches,
        "workdir": workdir,
        "ecu_file_path": ecu_file,
        "status": "uploaded"
    }

    return JSONResponse({
        "orderId": order_id,
        "detectedEcu": detected_ecu,
        "sourceFileName": os.path.basename(ecu_file),
        "sourceFileBytes": size,
        "isZip": bool(is_zip),
        "availablePatches": available_patches
    })

# Endpoint público para Wix
@router.get("/public/order/{order_id}")
def public_get_order(order_id: str):
    o = ORDERS_DB.get(order_id)
    if not o:
        raise HTTPException(404, "orderId not found")
    # OJO: no devuelvo paths internos
    return {
        "orderId": o["orderId"],
        "detectedEcu": o["detectedEcu"],
        "sourceFileName": o["sourceFileName"],
        "sourceFileBytes": o["sourceFileBytes"],
        "isZip": o["isZip"],
        "vehicle": o["vehicle"],
        "availablePatches": o["availablePatches"],
        "status": o["status"],
    }
