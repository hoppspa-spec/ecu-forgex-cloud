from fastapi import APIRouter, UploadFile, File, Form
from pathlib import Path
import zlib
import yaml

from app.services.patch_engine import create_patch, sha256

router = APIRouter(prefix="/admin", tags=["diff2patch"])

def crc32_hex(data: bytes) -> str:
    return f"{zlib.crc32(data) & 0xFFFFFFFF:08X}"

@router.post("/diff2patch")
async def diff2patch(
    ecu_type: str = Form(...),
    patch_id: str = Form(...),

    # opcional: para tu máscara offsets (texto libre)
    sw_number: str = Form(None),
    sw_offset: str = Form(None),
    mpc_type: str = Form(None),
    mpc_offset: str = Form(None),
    ecu_label: str = Form(None),
    ecu_offset: str = Form(None),

    stock: UploadFile = File(...),
    mod: UploadFile = File(...)
):
    stock_bytes = await stock.read()
    mod_bytes   = await mod.read()

    base_dir = Path("app/data/patches") / ecu_type / patch_id
    meta_core = create_patch(stock_bytes, mod_bytes, base_dir)

    meta = {
        "ecu_type": ecu_type,
        "patch_id": patch_id,

        "base": {
            "sha256": sha256(stock_bytes),
            "size_bytes": len(stock_bytes),
            "cvn_crc32": crc32_hex(stock_bytes),
            "original_filename": stock.filename,
        },

        "mod": {
            "sha256": sha256(mod_bytes),
            "size_bytes": len(mod_bytes),
            "cvn_crc32": crc32_hex(mod_bytes),
            "original_filename": mod.filename,
        },

        "patch": {
            "patch_size_bytes": meta_core["patch_size"],
        },

        # máscara offsets (tu formato)
        "offsets": {
            "sw_number": sw_number,
            "sw_offset": sw_offset,
            "mpc_type": mpc_type,
            "mpc_offset": mpc_offset,
            "ecu_type_label": ecu_label,
            "ecu_offset": ecu_offset,
        }
    }

    (base_dir / "meta.yaml").write_text(yaml.safe_dump(meta, sort_keys=False, allow_unicode=True))

    # Esto es “copy friendly” para ti:
    copy_block = (
        f"ECU={ecu_type}\n"
        f"PATCH={patch_id}\n"
        f"BASE_SHA256={meta['base']['sha256']}\n"
        f"BASE_SIZE={meta['base']['size_bytes']}\n"
        f"BASE_CVN={meta['base']['cvn_crc32']}\n"
        f"MOD_SHA256={meta['mod']['sha256']}\n"
        f"MOD_SIZE={meta['mod']['size_bytes']}\n"
        f"MOD_CVN={meta['mod']['cvn_crc32']}\n"
    )

    return {"status": "ok", "meta": meta, "copy": copy_block}
