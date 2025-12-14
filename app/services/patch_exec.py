from pathlib import Path
import json, yaml, zlib, bsdiff4

PATCH_ROOT = Path("static/patches")

def _to_bytes(hexstr: str) -> bytes:
    return bytes(int(x,16) for x in hexstr.split())

def _crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xffffffff

def _apply_yaml(bin_bytes: bytearray, recipe: dict) -> bytes:
    g = recipe.get("guards", {})
    if g.get("min_size") and len(bin_bytes) < int(g["min_size"]):
        raise ValueError("BIN demasiado pequeño")
    fam = g.get("family")
    if fam and recipe.get("id") and fam.upper() not in recipe.get("guards",{}).get("family","").upper():
        # sólo validatorio; puedes relajar si quieres
        pass

    for step in recipe.get("ops", []):
        if "patch" in step:
            pat = _to_bytes(step["patch"]["find_hex"])
            rep = _to_bytes(step["patch"]["replace_hex"])
            count = int(step["patch"].get("count", 1))
            hits = 0
            idx = bin_bytes.find(pat)
            while idx != -1 and hits < count:
                bin_bytes[idx:idx+len(pat)] = rep
                hits += 1
                idx = bin_bytes.find(pat, idx+len(rep))
            if hits < count:
                raise ValueError("Patrón no encontrado las veces requeridas")
        elif "write" in step:
            at = int(step["write"]["at"], 0)
            data = _to_bytes(step["write"]["hex"])
            bin_bytes[at:at+len(data)] = data

    for post in recipe.get("post", []):
        if "checksum" in post:
            typ = post["checksum"].get("type")
            if typ == "crc32":
                _ = _crc32(bin_bytes)  # si necesitas escribirlo, añade write_at
            # TODO: edc17_bosch, etc.

    return bytes(bin_bytes)

def apply_patch(family: str, patch_id: str, stock_bin: bytes) -> bytes:
    fam_dir = PATCH_ROOT / family.upper()
    if not fam_dir.exists():
        raise FileNotFoundError("Familia inexistente")

    # 1) YAML
    yml = fam_dir / f"{patch_id}.yml"
    if yml.exists():
        recipe = yaml.safe_load(yml.read_text(encoding="utf-8"))
        return _apply_yaml(bytearray(stock_bin), recipe)

    # 2) bsdiff
    bsd = fam_dir / f"{patch_id}.bsdiff"
    if bsd.exists():
        patch_data = bsd.read_bytes()
        return bsdiff4.patch(stock_bin, patch_data)

    # 3) overlay opcional
    ovl = fam_dir / f"{patch_id}.bin"
    meta = fam_dir / f"{patch_id}.meta.json"
    if ovl.exists() and meta.exists():
        m = json.loads(meta.read_text())
        at = int(m["at"], 0)
        buf = bytearray(stock_bin)
        chunk = ovl.read_bytes()
        buf[at:at+len(chunk)] = chunk
        return bytes(buf)

    raise FileNotFoundError("Parche no encontrado")
