from __future__ import annotations
import os, uuid, zipfile, shutil
from pathlib import Path
from typing import Optional, List, Tuple
import requests
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.routers import public_orders
app.include_router(public_orders.router)

# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------
app = FastAPI()

# ✅ CORS: permite llamadas desde Wix
# Si quieres estricto: ["https://www.hopp.cl", "https://*.wixsite.com", ...]
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


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class IngestPayload(BaseModel):
    vehicle: dict
    file: dict  # {originalName, sizeBytes, wixFileUrl}
    createdAt: str | None = None


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
ALLOWED_EXTS = {".bin", ".ori", ".mod", ".mpc", ".hex", ".s19", ".srec", ".e2p", ".eep", ".rom", ".frf"}
IGNORE_EXTS  = {".txt", ".nfo", ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".xml", ".json", ".csv", ".ini", ".log"}

def _looks_like_zip(head: bytes, content_type: str = "") -> bool:
    # ZIP magic: PK\x03\x04 or PK\x05\x06 (empty) or PK\x07\x08
    if head.startswith(b"PK\x03\x04") or head.startswith(b"PK\x05\x06") or head.startswith(b"PK\x07\x08"):
        return True
    ct = (content_type or "").lower()
    return "zip" in ct

def _iter_files(root: str) -> List[str]:
    out = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            out.append(os.path.join(dirpath, fn))
    return out

def pick_ecu_file(extract_dir: str) -> Optional[str]:
    """
    Elige el candidato ECU más probable:
    1) ignora basura por extensión típica
    2) prioriza extensiones conocidas
    3) prioriza el archivo más grande
    """
    candidates: List[Tuple[int, int, str]] = []  # (ext_score, size, path)

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

        ext_score = 0
        if ext in ALLOWED_EXTS:
            ext_score = 2
        elif ext == ".zip":
            ext_score = -5
        else:
            ext_score = 1  # sin extensión o rara: puede ser Trasdata

        low = name.lower()
        if any(k in low for k in ["readme", "info", "license", "metadata", "checksum", "md5", "sha", "project"]):
            ext_score -= 2

        candidates.append((ext_score, size, p))

    if not candidates:
        return None

    candidates.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return candidates[0][2]

def _save_stream_to_file(r: requests.Response, dst_path: str, head: bytes = b"") -> None:
    with open(dst_path, "wb") as f:
        if head:
            f.write(head)
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)

def _validate_size(path: str) -> int:
    size = os.path.getsize(path)
    if size < MIN_BYTES:
        raise HTTPException(400, f"ECU file too small: {size} bytes")
    if size > MAX_BYTES:
        raise HTTPException(400, f"ECU file too large: {size} bytes")
    return size

def _patches_placeholder():
    return [
        {"id":"speed_limiter", "name":"Speed Limiter OFF", "desc":"Remove or raise speed limiter.", "price":49, "tag":"Popular"},
        {"id":"dtc_off", "name":"DTC OFF", "desc":"Deactivate selected DTCs.", "price":39, "tag":"Fast"},
        {"id":"dpf_off", "name":"DPF OFF (off-road)", "desc":"Disable DPF (off-road only).", "price":99, "tag":"Diesel"},
    ]


# -----------------------------------------------------------------------------
# API: ingest from Wix file URL
# -----------------------------------------------------------------------------
@app.post("/api/ingest")
def ingest(payload: IngestPayload):
    wix_url = payload.file.get("wixFileUrl")
    if not wix_url:
        raise HTTPException(400, "Missing wixFileUrl")

    order_id = str(uuid.uuid4())
    workdir = os.path.join(TMP_DIR, order_id)
    os.makedirs(workdir, exist_ok=True)

    raw_path    = os.path.join(workdir, "upload.raw")
    zip_path    = os.path.join(workdir, "upload.zip")
    extract_dir = os.path.join(workdir, "extract")
    os.makedirs(extract_dir, exist_ok=True)

    # 1) Descargar stream
    try:
        r = requests.get(wix_url, timeout=60, stream=True, allow_redirects=True)
    except Exception as e:
        raise HTTPException(400, f"Failed to download from Wix: {e}")

    if r.status_code != 200:
        raise HTTPException(400, f"Failed to download from Wix (status {r.status_code})")

    # Peek
    try:
        head = next(r.iter_content(chunk_size=8))
    except StopIteration:
        head = b""

    content_type = r.headers.get("content-type", "")
    _save_stream_to_file(r, raw_path, head=head)

    is_zip = _looks_like_zip(head, content_type=content_type)

    ecu_file: Optional[str] = None
    if is_zip:
        shutil.copyfile(raw_path, zip_path)
        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(extract_dir)
        except zipfile.BadZipFile:
            raise HTTPException(400, "Invalid ZIP file (downloaded file is not a real ZIP)")

        ecu_file = pick_ecu_file(extract_dir)
        if not ecu_file:
            raise HTTPException(400, "No ECU file found inside ZIP")
    else:
        ecu_file = os.path.join(workdir, "ecu_input.bin")
        shutil.copyfile(raw_path, ecu_file)

    size = _validate_size(ecu_file)

    detected_ecu = payload.vehicle.get("ecu") or "UNKNOWN"

    return {
        "orderId": order_id,
        "detectedEcu": detected_ecu,
        "sourceFileName": os.path.basename(ecu_file),
        "sourceFileBytes": size,
        "isZip": bool(is_zip),
        "contentType": content_type,
        "availablePatches": _patches_placeholder(),
    }


# -----------------------------------------------------------------------------
# API: ingest multipart (direct upload to backend)
# -----------------------------------------------------------------------------
@app.post("/api/ingest-multipart")
async def ingest_multipart(
    file: UploadFile = File(...),
    brand: str = Form(""),
    model: str = Form(""),
    year: str = Form(""),
    engine: str = Form(""),
    ecu: str = Form(""),
):
    order_id = str(uuid.uuid4())
    workdir = os.path.join(TMP_DIR, order_id)
    os.makedirs(workdir, exist_ok=True)

    raw_path    = os.path.join(workdir, file.filename or "upload.bin")
    zip_path    = os.path.join(workdir, "upload.zip")
    extract_dir = os.path.join(workdir, "extract")
    os.makedirs(extract_dir, exist_ok=True)

    # Guardar upload a disco
    with open(raw_path, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)

    # Detectar ZIP por magic bytes (no por extensión)
    with open(raw_path, "rb") as f:
        head = f.read(8)

    content_type = (file.content_type or "")
    is_zip = _looks_like_zip(head, content_type=content_type)

    ecu_file: Optional[str] = None
    if is_zip:
        shutil.copyfile(raw_path, zip_path)
        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(extract_dir)
        except zipfile.BadZipFile:
            raise HTTPException(400, "Invalid ZIP file")

        ecu_file = pick_ecu_file(extract_dir)
        if not ecu_file:
            raise HTTPException(400, "No ECU file found inside ZIP")
    else:
        ecu_file = raw_path

    size = _validate_size(ecu_file)

    return {
        "orderId": order_id,
        "detectedEcu": ecu or "UNKNOWN",
        "sourceFileName": os.path.basename(ecu_file),
        "sourceFileBytes": size,
        "isZip": bool(is_zip),
        "contentType": content_type,
        "vehicle": {"brand":brand,"model":model,"year":year,"engine":engine,"ecu":ecu},
        "availablePatches": _patches_placeholder(),
    }


# -----------------------------------------------------------------------------
# UI: /upload page (drag & drop -> /api/ingest-multipart)
# -----------------------------------------------------------------------------
@app.get("/upload", response_class=HTMLResponse)
def upload_page(brand: str = "", model: str = "", year: str = "", engine: str = "", ecu: str = ""):
    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>EFX Upload</title>
  <style>
    body{{font-family:Arial;margin:0;background:#0b0f14;color:#fff;display:flex;min-height:100vh;align-items:center;justify-content:center}}
    .box{{width:min(720px,92vw);background:#111826;border:1px solid #1f2a3a;border-radius:16px;padding:22px}}
    .drop{{border:2px dashed #2b3b52;border-radius:14px;padding:26px;text-align:center;cursor:pointer}}
    .row{{display:flex;gap:12px;flex-wrap:wrap;margin-top:12px;opacity:.9;font-size:13px}}
    .pill{{background:#0b1220;border:1px solid #22324a;padding:6px 10px;border-radius:999px}}
    button{{margin-top:14px;width:100%;padding:12px 14px;border-radius:12px;border:0;background:#6d5efc;color:#fff;font-weight:700;cursor:pointer}}
    button:disabled{{opacity:.5;cursor:not-allowed}}
    .status{{margin-top:10px;white-space:pre-wrap;opacity:.9;font-size:13px}}
    input{{display:none}}
  </style>
</head>
<body>
  <div class="box">
    <h2 style="margin:0 0 10px 0;">Upload ECU file</h2>
    <div class="drop" id="drop">
      Drop your file here or click to browse<br/>
      <span style="opacity:.8;font-size:12px">BIN / ORI / MPC / E2P / ZIP (anything)</span>
    </div>
    <input type="file" id="file" />
    <div class="row">
      <div class="pill">Brand: {brand}</div>
      <div class="pill">Model: {model}</div>
      <div class="pill">Year: {year}</div>
      <div class="pill">Engine: {engine}</div>
      <div class="pill">ECU: {ecu}</div>
    </div>
    <button id="send" disabled>Upload & Continue</button>
    <div class="status" id="status">Waiting for file…</div>
  </div>

<script>
const drop = document.getElementById("drop");
const fileInput = document.getElementById("file");
const sendBtn = document.getElementById("send");
const statusEl = document.getElementById("status");
let selectedFile = null;

function setStatus(t){{ statusEl.textContent = t; }}

drop.addEventListener("click", () => fileInput.click());

["dragenter","dragover"].forEach(ev => drop.addEventListener(ev, e => {{
  e.preventDefault();
  drop.style.opacity = 0.85;
}}));
["dragleave","drop"].forEach(ev => drop.addEventListener(ev, e => {{
  e.preventDefault();
  drop.style.opacity = 1;
}}));

drop.addEventListener("drop", (e) => {{
  const f = e.dataTransfer.files?.[0];
  if (!f) return;
  selectedFile = f;
  setStatus(`Selected: ${{f.name}} ( ${{Math.round(f.size/1024)}} KB )`);
  sendBtn.disabled = false;
}});

fileInput.addEventListener("change", () => {{
  const f = fileInput.files?.[0];
  if (!f) return;
  selectedFile = f;
  setStatus(`Selected: ${{f.name}} ( ${{Math.round(f.size/1024)}} KB )`);
  sendBtn.disabled = false;
}});

sendBtn.addEventListener("click", async () => {{
  if (!selectedFile) return;
  sendBtn.disabled = true;
  setStatus("Uploading…");

  const fd = new FormData();
  fd.append("file", selectedFile);

  fd.append("brand", "{brand}");
  fd.append("model", "{model}");
  fd.append("year", "{year}");
  fd.append("engine", "{engine}");
  fd.append("ecu", "{ecu}");

  const res = await fetch("/api/ingest-multipart", {{ method:"POST", body: fd }});
  if (!res.ok) {{
    const txt = await res.text();
    setStatus("Upload failed:\\n" + txt);
    sendBtn.disabled = false;
    return;
  }}

  const data = await res.json();
  setStatus("OK ✅ Redirecting…\\nOrder: " + data.orderId);

  // vuelve a Wix con orderId
  const wixAnalyze = "https://www.hopp.cl/analyze";
  window.location.href = `${{wixAnalyze}}?orderId=${{encodeURIComponent(data.orderId)}}`;
}});
@app.get("/api/order/{order_id}")
def get_order(order_id: str):
    workdir = os.path.join(TMP_DIR, order_id)
    if not os.path.isdir(workdir):
        raise HTTPException(404, "Order not found")

    meta = {
        "orderId": order_id,
        "status": "ready",
        "detectedEcu": "EDC17",
        "availablePatches": [
            {"id":"speed_limiter","name":"Speed Limiter OFF","price":49},
            {"id":"dtc_off","name":"DTC OFF","price":39},
            {"id":"dpf_off","name":"DPF OFF","price":99},
        ]
    }
    return meta
</script>
</body>
</html>
"""
