import zipfile
import requests
from fastapi import UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests, zipfile, uuid, os

app = FastAPI()

# ✅ CORS: permite llamadas desde tu Wix
# Si quieres ultra estricto, reemplaza "*" por tu dominio exacto de Wix.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

TMP_DIR = os.getenv("EFX_TMP", "/tmp/efx")
os.makedirs(TMP_DIR, exist_ok=True)

MIN_BYTES = 32 * 1024
MAX_BYTES = 64 * 1024 * 1024

class IngestPayload(BaseModel):
    vehicle: dict
    file: dict  # {originalName, sizeBytes, wixFileUrl}
    createdAt: str | None = None

def pick_ecu_file(extract_dir: str) -> str | None:
    preferred_ext = (".bin", ".ori", ".mpc", ".e2p", ".dat", ".hex")
    best = None
    best_size = -1

    for root, _, files in os.walk(extract_dir):
        for name in files:
            p = os.path.join(root, name)
            lname = name.lower()
            size = os.path.getsize(p)

            # prioriza extensiones típicas, pero si no hay, igual podría servir
            if lname.endswith(preferred_ext):
                if size > best_size:
                    best = p
                    best_size = size

    if best:
        return best

    # fallback: cualquier archivo no vacío (por si viene sin extensión)
    for root, _, files in os.walk(extract_dir):
        for name in files:
            p = os.path.join(root, name)
            if os.path.getsize(p) > 0:
                return p

    return None

import os, uuid, zipfile, shutil, mimetypes
from pathlib import Path
from typing import Optional, List, Tuple

import requests
from fastapi import HTTPException

# Ajusta si quieres
ALLOWED_EXTS = {".bin", ".ori", ".mod", ".mpc", ".hex", ".s19", ".srec", ".e2p", ".eep", ".rom", ".frf"}
IGNORE_EXTS  = {".txt", ".nfo", ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".xml", ".json", ".csv", ".ini", ".log"}

def _safe_name(name: str) -> str:
    # Evita paths raros dentro del zip
    return os.path.basename(name).replace("\\", "_").replace("/", "_").strip() or "file"

def _looks_like_zip(head: bytes, content_type: str = "") -> bool:
    # ZIP magic: PK\x03\x04 or PK\x05\x06 (empty zip) or PK\x07\x08
    if head.startswith(b"PK\x03\x04") or head.startswith(b"PK\x05\x06") or head.startswith(b"PK\x07\x08"):
        return True
    # fallback por content-type
    ct = (content_type or "").lower()
    return "zip" in ct

def _iter_files(root: str) -> List[str]:
    files = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            files.append(full)
    return files

def pick_ecu_file(extract_dir: str) -> Optional[str]:
    """
    Elige el candidato ECU más probable:
    1) ignora basura por extensión típica
    2) prioriza extensiones conocidas
    3) prioriza el archivo más grande (normalmente el dump real)
    """
    candidates: List[Tuple[int, int, str]] = []  # (ext_score, size, path)

    for p in _iter_files(extract_dir):
        name = os.path.basename(p)
        ext = Path(name).suffix.lower()

        # ignora archivos vacíos o minúsculos
        try:
            size = os.path.getsize(p)
        except OSError:
            continue
        if size <= 0:
            continue

        # ignora basura conocida
        if ext in IGNORE_EXTS:
            continue

        # score por extensión
        ext_score = 0
        if ext in ALLOWED_EXTS:
            ext_score = 2
        elif ext == ".zip":
            # zip dentro de zip? lo ignoramos por ahora (si quieres, lo soportamos después)
            ext_score = -5
        else:
            # sin extensión o extensión rara: igual puede ser ECU (Trasdata, etc.)
            ext_score = 1

        # penaliza nombres típicos de metadata
        low = name.lower()
        if any(k in low for k in ["readme", "info", "license", "metadata", "checksum", "md5", "sha", "project"]):
            ext_score -= 2

        candidates.append((ext_score, size, p))

    if not candidates:
        return None

    # orden: mayor score, mayor tamaño
    candidates.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return candidates[0][2]

def _save_response_content(r: requests.Response, dst_path: str) -> None:
    # stream a disco para no reventar RAM si el archivo crece
    with open(dst_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)

@app.post("/api/ingest")
def ingest(payload: IngestPayload):
    wix_url = payload.file.get("wixFileUrl")
    if not wix_url:
        raise HTTPException(400, "Missing wixFileUrl")

    order_id = str(uuid.uuid4())
    workdir = os.path.join(TMP_DIR, order_id)
    os.makedirs(workdir, exist_ok=True)

    # Paths
    raw_path     = os.path.join(workdir, "upload.raw")
    zip_path     = os.path.join(workdir, "upload.zip")
    extract_dir  = os.path.join(workdir, "extract")
    os.makedirs(extract_dir, exist_ok=True)

    # 1) Descargar (mejor con stream)
    try:
        r = requests.get(wix_url, timeout=60, stream=True, allow_redirects=True)
    except Exception as e:
        raise HTTPException(400, f"Failed to download from Wix: {e}")

    if r.status_code != 200:
        raise HTTPException(400, f"Failed to download from Wix (status {r.status_code})")

    # Peek de cabecera para detectar ZIP de verdad
    head = b""
    try:
        head = next(r.iter_content(chunk_size=8))
    except StopIteration:
        head = b""

    content_type = r.headers.get("content-type", "")

    # Guardamos todo el archivo (incluyendo el head que ya leímos)
    with open(raw_path, "wb") as f:
        if head:
            f.write(head)
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)

    # 2) Decidir si es ZIP o archivo directo
    is_zip = _looks_like_zip(head, content_type=content_type)

    ecu_file: Optional[str] = None

    if is_zip:
        # renombrar raw -> zip
        shutil.copyfile(raw_path, zip_path)

        # unzip
        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(extract_dir)
        except zipfile.BadZipFile:
            # a veces Wix devuelve HTML aunque el content-type diga zip
            # deja un error más explícito
            raise HTTPException(400, "Invalid ZIP file (downloaded file is not a real ZIP)")

        # 3) encontrar archivo interno
        ecu_file = pick_ecu_file(extract_dir)
        if not ecu_file:
            raise HTTPException(400, "No ECU file found inside ZIP")
    else:
        # Archivo directo (BIN/MPC/sin extensión)
        # lo movemos a un nombre estable
        ecu_file = os.path.join(workdir, "ecu_input.bin")
        shutil.copyfile(raw_path, ecu_file)

    # 4) Validación tamaño
    size = os.path.getsize(ecu_file)
    if size < MIN_BYTES:
        raise HTTPException(400, f"ECU file too small: {size} bytes")
    if size > MAX_BYTES:
        raise HTTPException(400, f"ECU file too large: {size} bytes")

    # 5) detección placeholder (V1: usar ecu del formulario)
    detected_ecu = payload.vehicle.get("ecu") or "UNKNOWN"

    # 6) patches placeholder (V1)
    available_patches = [
        {"id":"speed_limiter", "name":"Speed Limiter OFF", "desc":"Remove or raise speed limiter.", "price":49, "tag":"Popular"},
        {"id":"dtc_off", "name":"DTC OFF", "desc":"Deactivate selected DTCs.", "price":39, "tag":"Fast"},
        {"id":"dpf_off", "name":"DPF OFF (off-road)", "desc":"Disable DPF (off-road only).", "price":99, "tag":"Diesel"},
    ]

    return {
        "orderId": order_id,
        "detectedEcu": detected_ecu,
        "sourceFileName": os.path.basename(ecu_file),
        "sourceFileBytes": size,
        "isZip": bool(is_zip),
        "contentType": content_type,
        "availablePatches": available_patches
    }


