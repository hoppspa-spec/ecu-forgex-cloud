from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.services.families import list_families, detect_family, list_patches_for_family
from app.services.patch_exec import apply_patch

router = APIRouter()

@router.get("/public/families")
def api_families():
    return {"families": list_families()}

@router.post("/analyze_bin")
async def analyze_bin(bin_file: UploadFile = File(...)):
    data = await bin_file.read()
    # CVN y tamaño
    import zlib
    cvn = zlib.crc32(data) & 0xffffffff
    # texto para probar detectores
    from app.util.bin_text import bin_to_text
    txt = bin_to_text(data)
    fam = detect_family(None, bin_file.filename, txt)
    return {
        "filename": bin_file.filename,
        "bin_size": len(data),
        "cvn_crc32": f"{cvn:08X}",
        "ecu_type": fam or "Desconocida",
        "ecu_part_number": None
    }

@router.get("/public/patches")
def api_patches(family: str, brand: str|None=None):
    return {"family": family, "patches": list_patches_for_family(family, brand)}

@router.post("/public/apply")
async def api_apply(family: str = Form(...), patch_id: str = Form(...), bin_file: UploadFile = File(...)):
    stock = await bin_file.read()
    try:
        out = apply_patch(family, patch_id, stock)
    except Exception as e:
        raise HTTPException(400, f"{e}")
    # Devuelve archivo mod (o crea orden/checkout si lo prefieres)
    from fastapi.responses import StreamingResponse
    import io
    return StreamingResponse(io.BytesIO(out), media_type="application/octet-stream",
                             headers={"Content-Disposition": f'attachment; filename="{patch_id}.bin"'})
