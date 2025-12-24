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

@app.post("/api/ingest")
def ingest(payload: IngestPayload):
    wix_url = payload.file.get("wixFileUrl")
    if not wix_url:
        raise HTTPException(400, "Missing wixFileUrl")

    order_id = str(uuid.uuid4())
    workdir = os.path.join(TMP_DIR, order_id)
    os.makedirs(workdir, exist_ok=True)

    zip_path = os.path.join(workdir, "upload.zip")
    extract_dir = os.path.join(workdir, "extract")
    os.makedirs(extract_dir, exist_ok=True)

    # 1) descargar zip
    r = requests.get(wix_url, timeout=60)
    if r.status_code != 200:
        raise HTTPException(400, "Failed to download from Wix")

    with open(zip_path, "wb") as f:
        f.write(r.content)

    # 2) unzip
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(extract_dir)
    except zipfile.BadZipFile:
        raise HTTPException(400, "Invalid ZIP file")

    # 3) encontrar archivo interno
    ecu_file = pick_ecu_file(extract_dir)
    if not ecu_file:
        raise HTTPException(400, "No ECU file found inside ZIP")

    size = os.path.getsize(ecu_file)
    if size < MIN_BYTES:
        raise HTTPException(400, f"ECU file too small: {size} bytes")
    if size > MAX_BYTES:
        raise HTTPException(400, f"ECU file too large: {size} bytes")

    # 4) detección placeholder (V1: usar ecu del formulario)
    detected_ecu = payload.vehicle.get("ecu") or "UNKNOWN"

    # 5) patches placeholder (V1)
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
        "availablePatches": available_patches
    }
