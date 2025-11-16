from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from pathlib import Path
import subprocess
import uuid
import json

# -------------------------------------------------------------------
# Rutas base
#  - Este archivo está en app/main.py
#  - El index.html está en /static a nivel raíz del proyecto
# -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent       # .../app
PROJECT_ROOT = BASE_DIR.parent                   # raíz del repo

STATIC = PROJECT_ROOT / "static"
STORAGE = PROJECT_ROOT / "storage"

STORAGE.mkdir(exist_ok=True)
STATIC.mkdir(exist_ok=True)

# -------------------------------------------------------------------
# App
# -------------------------------------------------------------------
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


# -------------------------------------------------------------------
# PATCH BIN (generar Bin.MOD real)
# -------------------------------------------------------------------
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


# -------------------------------------------------------------------
# ANALYZE BIN (Paso 1: mostrar info ECU + opciones de parche)
# -------------------------------------------------------------------
@app.post("/analyze_bin")
async def analyze_bin(bin_file: UploadFile = File(...)):
    """
    Paso 1: analiza el BIN y devuelve información básica de la ECU
    + qué opciones de parche están disponibles.
    Más adelante aquí va tu lógica real de detección.
    """

    filename = bin_file.filename or ""
    contents = await bin_file.read()   # bytes del BIN
    size = len(contents)

    # --- LÓGICA DUMMY SOLO PARA PROBAR FRONT ---
    upper_name = filename.upper()

    if "MED17" in upper_name:
        ecu_type = "MED17.3.9"
        ecu_part_number = "03C906024"
        manufacturer_number = "Bosch 0261"
    else:
        ecu_type = "Desconocida"
        ecu_part_number = "No disponible"
        manufacturer_number = "No disponible"

    available_patches = [
        {
            "id": "dtc_disable",
            "label": "Deshabilitar DTC",
            "description": "Desactivar códigos de avería seleccionados."
        },
        {
            "id": "dp_dpf_egr",
            "label": "Paquete DPF/EGR",
            "description": "Aplicar lógica de anulación para DPF y EGR."
        },
    ]
    # --- FIN LÓGICA DUMMY ---

    return {
        "filename": filename,
        "bin_size": size,
        "ecu_type": ecu_type,
        "ecu_part_number": ecu_part_number,
        "manufacturer_number": manufacturer_number,
        "available_patches": available_patches,
    }
