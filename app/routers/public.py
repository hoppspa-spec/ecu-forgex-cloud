from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Dict

router = APIRouter(tags=["public"])

@router.get("/")
def root():
    return {"name": "ECU Forge X API", "status": "ok"}

@router.post("/analyze_bin")
async def analyze_bin(bin_file: UploadFile = File(...)) -> Dict:
    data = await bin_file.read()
    size = len(data)

    # TODO: aquí llamas a tu analizador real si ya lo tienes
    # from app.services.analyze import analyze_bin_bytes
    # info = analyze_bin_bytes(data)

    # Demo estable (no rompe el front)
    info = {
        "analysis_id": "demo-anl-1",
        "filename": bin_file.filename,
        "bin_size": size,
        "ecu_type": "Desconocida",         # reemplaza cuando detectes
        "ecu_part_number": None,
        "software_number": None,
    }
    return info

@router.get("/patches")
def list_patches():
    # TODO: leer desde /static/patches o desde store/recipes
    return {"patches": [], "packs": []}
