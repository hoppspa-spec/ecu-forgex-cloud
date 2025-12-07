from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os
import shutil


# ================================
# CONFIGURACIÓN GENERAL
# ================================
ROOT_DIR = Path(__file__).resolve().parent
STATIC_DIR = ROOT_DIR / "static"
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT_DIR / "storage"))

DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="ECU FORGE X API")


# ================================
# ARCHIVOS ESTÁTICOS
# ================================
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ================================
# RUTA PRINCIPAL (REDIRECT A UI)
# ================================
@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


# ================================
# HEALTHCHECK
# ================================
@app.get("/health")
def health():
    return {"ok": True, "status": "running"}


# ================================
# ENDPOINT: ANALIZAR BIN
# ================================
@app.post("/analyze_bin")
async def analyze_bin(file: UploadFile = File(...)):
    """
    Analiza el archivo BIN y devuelve parches disponibles.
    EN ESTA ETAPA: se usa un mock, pero ya es funcional con el frontend.
    """

    if not file.filename.lower().endswith(".bin"):
        raise HTTPException(status_code=400, detail="Archivo debe ser .BIN")

    # Guardar BIN en /storage
    bin_path = DATA_DIR / file.filename

    with open(bin_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # ======================
    # ⚠ MOCK – PARTE TEMPORAL
    # Luego lo reemplazamos por el analizador real
    # ======================
    fake_patches = [
        {"id": "speed_limiter", "label": "Speed Limiter"},
        {"id": "rpm_limit", "label": "RPM Limit Increase"},
        {"id": "dtc_off", "label": "DTC OFF (General)"}
    ]

    return {
        "ecu_type": "Bosch MG1 (mock)",
        "file_saved": str(bin_path),
        "available_patches": fake_patches,
    }


# ================================
# ENDPOINT: CREAR MOD (MOCK POR AHORA)
# ================================
@app.post("/create_mod")
async def create_mod(patch_id: str, original_file: str):
    """
    Genera un archivo MOD (mock). Más adelante conectamos el generador real.
    """

    mod_path = DATA_DIR / f"{patch_id}_generated.MOD"

    # Crear archivo dummy
    with open(mod_path, "w") as f:
        f.write(f"MOD generado para parche: {patch_id}\nArchivo original: {original_file}")

    return {
        "mod_file": str(mod_path),
        "message": "Archivo MOD generado correctamente"
    }


# ================================
# DESCARGAR ARCHIVO MOD
# ================================
@app.get("/download_mod")
def download_mod(path: str):
    file_path = Path(path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        filename=file_path.name
    )

