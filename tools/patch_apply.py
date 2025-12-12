# tools/patch_apply.py
from pathlib import Path
import binascii, yaml, re

def _clean_hex(s):
    return bytes.fromhex(re.sub(r'[^0-9A-Fa-f]', '', s))

def _apply_ops(blob: bytearray, ops):
    for op in ops:
        hfind = _clean_hex(op["find"])
        hrep  = _clean_hex(op["replace"])
        idx = 0; hits = 0
        while True:
            pos = blob.find(hfind, idx)
            if pos < 0: break
            blob[pos:pos+len(hrep)] = hrep
            idx = pos + len(hrep); hits += 1
        # opcional: exigir al menos 1 hit por op
        # if hits == 0: raise RuntimeError(f"Pattern not found: {op['find']}")
    return blob

def apply_patch(src_path: str, dst_path: str, patch_id: str):
    src = Path(src_path); dst = Path(dst_path)
    # Detectar familia según nombre destino (MD1, MEVD17, etc.)
    fam = "GENERIC"
    for key in ("MD1","EDC17","MEVD17","MED17","MG1","ME7"):
        if key in dst.name.upper():
            fam = "MEVD17" if key=="MED17" else key
            break

    recipes_root = Path(__file__).resolve().parent.parent / "storage" / "recipes"
    # probar ruta directa y fallback por familia
    candidates = [
        recipes_root / fam / f"{patch_id}.yml",
        recipes_root / "MEVD17" / f"{patch_id}.yml",
        recipes_root / "MD1"    / f"{patch_id}.yml",
    ]
    yml = next((p for p in candidates if p.exists()), None)
    if not yml:
        # si no hay receta, copia tal cual
        dst.write_bytes(src.read_bytes())
        return

    data = src.read_bytes()
    recipe = yaml.safe_load(yml.read_text(encoding="utf-8"))
    ops = recipe.get("ops", [])
    out = _apply_ops(bytearray(data), ops)
    dst.write_bytes(out)
