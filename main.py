from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import upload
from app.routers import ingest

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)     # GET /upload
app.include_router(ingest.router)     # POST /api/ingest-multipart + GET /api/public/order/...

@app.get("/health")
def health():
    return {"ok": True}

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import os, uuid, zipfile, shutil

app = FastAPI()

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

ALLOWED_EXTS = {".bin", ".ori", ".mod", ".mpc", ".hex", ".s19", ".srec", ".e2p", ".eep", ".rom", ".frf"}
IGNORE_EXTS  = {".txt", ".nfo", ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".xml", ".json", ".csv", ".ini", ".log"}

def pick_ecu_file(extract_dir: str):
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

            score = 1  # raro/sin extensión igual sirve
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

    <div class="row">
      <div class="pill">Brand: {brand}</div>
      <div class="pill">Model: {model}</div>
      <div class="pill">Year: {year}</div>
      <div class="pill">Engine: {engine}</div>
      <div class="pill">ECU: {ecu}</div>
    </div>

    <div class="drop" id="drop" style="margin-top:12px;">
      Drop your file here or click to browse<br/>
      <span style="opacity:.8;font-size:12px">BIN / ORI / MPC / ZIP / no-extension (any)</span>
    </div>

    <input type="file" id="file" />
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
  e.preventDefault(); drop.style.opacity = 0.85;
}}));
["dragleave","drop"].forEach(ev => drop.addEventListener(ev, e => {{
  e.preventDefault(); drop.style.opacity = 1;
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
  const txt = await res.text();

  if (!res.ok) {{
    setStatus("Upload failed:\\n" + txt);
    sendBtn.disabled = false;
    return;
  }}

  const data = JSON.parse(txt);
  setStatus("OK ✅ Redirecting…\\nOrder: " + data.orderId);

  // vuelve a Wix
  window.location.href = `https://hopp.cl/analyze?orderId=${{encodeURIComponent(data.orderId)}}`;
}});
</script>
</body>
</html>
"""

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
    workdir = os.path.join(TMP_DIR, order_id)
    os.makedirs(workdir, exist_ok=True)

    raw_path = os.path.join(workdir, file.filename or "upload.bin")
    with open(raw_path, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)

    extract_dir = os.path.join(workdir, "extract")
    os.makedirs(extract_dir, exist_ok=True)

    ecu_file = raw_path
    if (file.filename or "").lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(raw_path, "r") as z:
                z.extractall(extract_dir)
        except zipfile.BadZipFile:
            raise HTTPException(400, "Invalid ZIP file")

        ecu_file = pick_ecu_file(extract_dir)
        if not ecu_file:
            raise HTTPException(400, "No ECU file found inside ZIP")

    size = os.path.getsize(ecu_file)
    if size < MIN_BYTES:
        raise HTTPException(400, f"ECU file too small: {size} bytes")
    if size > MAX_BYTES:
        raise HTTPException(400, f"ECU file too large: {size} bytes")

    detected_ecu = ecu or "UNKNOWN"

    # TODO: aquí guardas order a DB real (por ahora demo)
    return {
        "orderId": order_id,
        "detectedEcu": detected_ecu,
        "sourceFileName": os.path.basename(ecu_file),
        "sourceFileBytes": size,
        "vehicle": {"brand":brand,"model":model,"year":year,"engine":engine,"ecu":ecu},
        "availablePatches": [
            {"id":"speed_limiter", "name":"Speed Limiter OFF", "price":49},
            {"id":"dtc_off", "name":"DTC OFF", "price":39},
            {"id":"dpf_off", "name":"DPF OFF (off-road)", "price":99},
        ]
    }
