from fastapi import APIRouter, UploadFile, File
import zlib
from app.services.patch_engine import sha256

router = APIRouter(prefix="/admin", tags=["fingerprint"])

def crc32_hex(data: bytes) -> str:
    return f"{zlib.crc32(data) & 0xFFFFFFFF:08X}"

@router.post("/fingerprint")
async def fingerprint(bin_file: UploadFile = File(...)):
    data = await bin_file.read()
    out = {
        "filename": bin_file.filename,
        "size_bytes": len(data),
        "sha256": sha256(data),
        "cvn_crc32": crc32_hex(data),
    }
    out["copy"] = (
        f"SHA256={out['sha256']}\n"
        f"SIZE={out['size_bytes']}\n"
        f"CVN={out['cvn_crc32']}\n"
    )
    return out
