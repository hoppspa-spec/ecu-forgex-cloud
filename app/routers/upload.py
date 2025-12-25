from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["upload"])

@router.get("/upload", response_class=HTMLResponse)
def upload_page(brand: str = "", model: str = "", year: str = "", engine: str = "", ecu: str = ""):
    # Página drag & drop. Sube a /api/ingest-multipart y luego vuelve a Wix /analyze?orderId=...
    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>EFX Upload</title>
  <style>
    body{{font-family:Arial;margin:0;background:#0b0f14;color:#fff;display:flex;min-height:100vh;align-items:center;justify-content:center}}
    .box{{width:min(760px,92vw);background:#111826;border:1px solid #1f2a3a;border-radius:16px;padding:22px}}
    .drop{{border:2px dashed #2b3b52;border-radius:14px;padding:26px;text-align:center;cursor:pointer}}
    .row{{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0;opacity:.9;font-size:13px}}
    .pill{{background:#0b1220;border:1px solid #22324a;padding:6px 10px;border-radius:999px}}
    button{{margin-top:10px;width:100%;padding:12px 14px;border-radius:12px;border:0;background:#6d5efc;color:#fff;font-weight:700;cursor:pointer}}
    button:disabled{{opacity:.5;cursor:not-allowed}}
    .status{{margin-top:10px;white-space:pre-wrap;opacity:.9;font-size:13px}}
    input{{display:none}}
  </style>
</head>
<body>
  <div class="box">
    <h2 style="margin:0 0 10px 0;">Upload ECU file</h2>

    <div class="row">
      <div class="pill">Brand: <b>{brand}</b></div>
      <div class="pill">Model: <b>{model}</b></div>
      <div class="pill">Year: <b>{year}</b></div>
      <div class="pill">Engine: <b>{engine}</b></div>
      <div class="pill">ECU: <b>{ecu}</b></div>
    </div>

    <div class="drop" id="drop">
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
  setStatus(`Selected: ${{f.name}} (${{Math.round(f.size/1024)}} KB)`);
  sendBtn.disabled = false;
}});

fileInput.addEventListener("change", () => {{
  const f = fileInput.files?.[0];
  if (!f) return;
  selectedFile = f;
  setStatus(`Selected: ${{f.name}} (${{Math.round(f.size/1024)}} KB)`);
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

  // vuelve a Wix analyze con orderId
  window.location.href = `https://www.hopp.cl/analyze?orderId=${{encodeURIComponent(data.orderId)}}`;
}});
</script>
</body>
</html>
"""
