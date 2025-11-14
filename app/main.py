from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from pathlib import Path
import subprocess
import uuid
import os
import json

BASE_DIR = Path(__file__).parent
STORAGE = BASE_DIR / "storage"
STATIC = BASE_DIR / "static"

STORAGE.mkdir(exist_ok=True)
STATIC.mkdir(exist_ok=True)

app = FastAPI(
    title="ECU FORGE X",
    version="1.0.0",
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # luego lo limitas a tu dominio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Servir HTML /static/index.html ---
app.mount("/static", StaticFiles(directory=STATIC), name="static")

@app.get("/", response_class=HTMLResponse)
def index():
    index_path = STATIC / "index.html"
    if not index_path.exists():
        return HTMLResponse("<h1>ECU FORGE X</h1><p>Falta static/index.html</p>")
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


@app.post("/patch_bin")
async def patch_bin(bin_file: UploadFile = File(...), descriptor: UploadFile = File(...)):

    job_id = str(uuid.uuid4())
    job_dir = STORAGE / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # rutas de entrada
    bin_path = job_dir / f"original_{bin_file.filename}"
    desc_path = job_dir / f"descriptor_{descriptor.filename}"
    out_dir = job_dir / "out"
    out_dir.mkdir(exist_ok=True)

    # guardar archivos subidos
    with open(bin_path, "wb") as f:
        f.write(await bin_file.read())

    with open(desc_path, "wb") as f:
        f.write(await descriptor.read())

    # ejecutar tu CLI patcher usando el módulo app.patcher_cli
    cmd = [
        "python",
        "-m", "app.patcher_cli",
        "--bin", str(bin_path),
        "--descriptor", str(desc_path),
        "--out", str(out_dir),
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            return JSONResponse(
                status_code=500,
                content={
                    "error": "patcher_failed",
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                },
            )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "exception", "detail": str(e)})

    # buscar el Bin.MOD que generó el patcher
    binmods = list(out_dir.glob("*Bin.MOD.zip"))
    if not binmods:
        # si tu patcher genera otro nombre, ajusta este patrón
        return JSONResponse(status_code=500, content={"error": "no_binmod_generated"})

    binmod_path = binmods[0]

    # guardar estado mínimo
    state = {
        "job_id": job_id,
        "bin_file": str(bin_path),
        "descriptor": str(desc_path),
        "binmod": str(binmod_path),
    }
    (job_dir / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")

    # devolver archivo directamente
    return FileResponse(
        path=str(binmod_path),
        filename=binmod_path.name,
        media_type="application/zip",
    )
