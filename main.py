from __future__ import annotations

import os, uuid, zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from app.routers.orders import router as orders_router
from app.routers.public_orders import router as public_orders_router
from app.routers.downloads import router as downloads_router

from app.services.store import order_dir, save_order

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(orders_router)
app.include_router(public_orders_router)
app.include_router(downloads_router)

@app.get("/health")
def health():
    return {"ok": True}

MIN_BYTES = 32 * 1024
MAX_BYTES = 64 * 1024 * 1024

ALLOWED_EXTS = {".bin", ".ori", ".mod", ".mpc", ".hex", ".s19", ".srec", ".e2p", ".eep", ".rom", ".frf"}
IGNORE_EXTS  = {".txt", ".nfo", ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".xml", ".json", ".csv", ".ini", ".log"}

def pick_ecu_file(extract_dir: str) -> Optional[str]:
    best = None
    best_score = -999
    best_size = -1

    for root, _, files in os.walk(extract_dir):
        for name in files:
            p = os.path.join(root, name)
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            if size <= 0:
                continue

            ext = os.path.splitext(name)[1].lower()
            if ext in IGNORE_EXTS:
                continue

            score = 1
            if ext in ALLOWED_EXTS:
                score = 3
            if ext == ".zip":
                score = -5

            low = name.lower()
            if any(k in low for k in ["readme", "info", "license", "metadata", "checksum", "md5", "sha", "project"]):
                score -= 2

            if (score > best_score) or (score == best_score and size > best_size):
                best = p
                best_score = score
                best_size = size

    return best

@app.get("/upload", response_class=HTMLResponse)
def upload_page(brand: str = "", model: str = "", year: str = "", engine: str = "", ecu: str = ""):
    return f"""<!doctype html>
<html>
<head> ... (tu HTML igual, sin cambios) ... </head>
<body> ... </body>
</html>"""

@app.post("/api/ingest-multipart")
async def ingest_multipart(
    file: UploadFile = File(...),
    brand: str = Form(""),
    model: str = Form(""),
    year: str = Form(""),
    engine: str = Form(""),
    ecu: str = Form("")
):
    order_id = str(uuid.uuid4())
    workdir = order_dir(order_id)

    filename = file.filename or "upload.bin"
    raw_path = workdir / filename

    with open(raw_path, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)

    extract_dir = workdir / "extract"
    extract_dir.mkdir(parents=True, exist_ok=True)

    ecu_file = str(raw_path)
    if filename.lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(str(raw_path), "r") as z:
                z.extractall(str(extract_dir))
        except zipfile.BadZipFile:
            raise HTTPException(400, "Invalid ZIP file")

        chosen = pick_ecu_file(str(extract_dir))
        if not chosen:
            raise HTTPException(400, "No ECU file found inside ZIP")
        ecu_file = chosen

    size = os.path.getsize(ecu_file)
    if size < MIN_BYTES:
        raise HTTPException(400, f"ECU file too small: {size} bytes")
    if size > MAX_BYTES:
        raise HTTPException(400, f"ECU file too large: {size} bytes")

    order = {
        "id": order_id,
        "created_at": datetime.utcnow().isoformat(),
        "status": "pending_patch",
        "paid": False,
        "download_ready": False,
        "family": ecu or "UNKNOWN",
        "engine": engine or "",
        "sourceFileName": os.path.basename(ecu_file),
        "sourceFileBytes": size,
        "original_filename": filename,
        "vehicle": {"brand": brand, "model": model, "year": year, "engine": engine, "ecu": ecu},
        "availablePatches": [
            {"id":"speed_limiter", "name":"Speed Limiter OFF", "price":49},
            {"id":"dtc_off", "name":"DTC OFF", "price":39},
            {"id":"dpf_off", "name":"DPF OFF (off-road)", "price":99},
        ],
        "checkout_url": f"/static/checkout.html?order_id={order_id}",
        # cuando generes mod:
        "mod_file_path": None,
    }

    save_order(order_id, order)

    return {
        "orderId": order_id,
        "detectedEcu": order.get("family"),
        "sourceFileName": order.get("sourceFileName"),
        "sourceFileBytes": order.get("sourceFileBytes"),
        "vehicle": order.get("vehicle"),
        "availablePatches": order.get("availablePatches"),
    }
