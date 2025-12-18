import hashlib
import bsdiff4
from pathlib import Path

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def create_patch(stock: bytes, mod: bytes, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    base_hash = sha256(stock)
    patch_bytes = bsdiff4.diff(stock, mod)

    (out_dir / "patch.bsdiff").write_bytes(patch_bytes)
    (out_dir / "base.sha256").write_text(base_hash)

    meta = {
        "base_sha256": base_hash,
        "base_size": len(stock),
        "patch_size": len(patch_bytes)
    }

    return meta

def apply_patch(stock: bytes, patch_dir: Path) -> bytes:
    expected = (patch_dir / "base.sha256").read_text().strip()
    current = sha256(stock)

    if expected != current:
        raise ValueError("STOCK no coincide con el parche")

    patch = (patch_dir / "patch.bsdiff").read_bytes()
    return bsdiff4.patch(stock, patch)
