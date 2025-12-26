from __future__ import annotations

import os, uuid, zipfile
from pathlib import Path
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.services.storage import save_order

router = APIRouter(prefix="/api", tags=["ingest"])

MIN_BYTES = 32 * 1024
MAX_BYTES = 64 * 1024 * 1024

ALLOWED_EXTS = {".bin", ".ori", ".mod", ".mpc", ".hex", ".s19", ".srec", ".e2p", ".eep", ".rom", ".frf"}
IGNORE_EXTS  = {".txt", ".nfo", ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".xml", ".json", ".csv", ".ini", ".log"}

DATA_DIR = Path(os.getenv("DATA_DIR", "/storage/efx"))
ORDERS_DIR = DATA_DIR / "orders"
ORDERS_DIR.mkdir(parents=True, exist_ok=True)


def pick_ecu_file(extract_dir: Path) -> Optional[Path]:
    best = None
    best_score = -999
    best_size = -1

    for p in extract_dir.rglob("*"):
        if not p.is_file():
            continue

        size = p.stat().st_size
        if size <= 0:
            continue

        ext = p.suffix.lower()
        if ext in IGNORE_EXTS:
            continue

        score = 1
        if ext in ALLOWED_EXTS:
            score = 3
        if ext == ".zip":
            score = -5

        low = p.name.lower()
        if any(k in low for k in ["readme", "info", "license", "checksum", "md5", "sha"]):
            score -= 2

        if score > best_score or (score == best_score and size > best_size):
            best = p
            best_score = score
            best_size = size

    return best


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
    workdir = ORDERS_DIR / order_id
    workdir.mkdir(parents=True, exist_ok=True)

    raw_path = workdir / (file.filename or "upload.bin")

    with open(raw_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)

    ecu_file = raw_path

    if raw_path.suffix.lower() == ".zip":
        extract_dir = workdir / "extract"
        extract_dir.mkdir()
        try:
            with zipfile.ZipFile(raw_path) as z:
                z.extractall(extract_dir)
        except zipfile.BadZipFile:
            raise HTTPException(400, "Invalid ZIP")

        picked = pick_ecu_file(extract_dir)
        if not picked:
            raise HTTPException(400, "No ECU file found in ZIP")
        ecu_file = picked

    size = ecu_file.stat().st_size
    if size < MIN_BYTES:
        raise HTTPException(400, "File too small")
    if size > MAX_BYTES:
        raise HTTPException(400, "File too large")

    order = {
        "id": order_id,
        "created_at": datetime.utcnow().isoformat(),
        "status": "uploaded",
        "paid": False,
        "download_ready": False,
        "detectedEcu": ecu or "UNKNOWN",
        "sourceFileName": ecu_file.name,
        "sourceFileBytes": size,
        "vehicle": {
            "brand": brand,
            "model": model,
            "year": year,
            "engine": engine,
            "ecu": ecu,
        },
        "availablePatches": [
            {"id": "speed_limiter", "name": "Speed Limiter OFF", "price": 49},
            {"id": "dtc_off", "name": "DTC OFF", "price": 39},
            {"id": "dpf_off", "name": "DPF OFF (off-road)", "price": 99},
        ],
    }

    save_order(order_id, order)

    return {"orderId": order_id}
