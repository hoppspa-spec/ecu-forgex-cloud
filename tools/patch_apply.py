# tools/patch_apply.py
from __future__ import annotations
import json, re, os
from pathlib import Path
from typing import List, Dict, Optional

# -----------------------------------------------------------------------------------
# Rutas (auto-descubiertas). Puedes forzar con env: EFX_RECIPES_DIR / EFX_STATIC_DIR
# -----------------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR   = Path(os.getenv("EFX_STATIC_DIR", ROOT / "static"))
STORAGE_DIR  = Path(os.getenv("DATA_DIR",      ROOT / "storage"))
RECIPES_DIR  = Path(os.getenv("EFX_RECIPES_DIR", STORAGE_DIR / "recipes"))
PATCHES_JSON = STATIC_DIR / "patches" / "global.json"
PACKS_JSON   = STATIC_DIR / "patches" / "packs.json"

# -----------------------------------------------------------------------------------
# Utilidades
# -----------------------------------------------------------------------------------
def _hex_to_bytes(hex_s: str) -> bytes:
    """
    Convierte "AA BB ?? 11" en bytes con comodín (??) soportado.
    Retorna bytes y una máscara (mismo largo) donde 1=byte relevante, 0=wildcard.
    """
    parts = re.split(r"[\s,]+", hex_s.strip())
    buf = bytearray()
    mask = bytearray()
    for p in parts:
        if p == "" or p is None:
            continue
        if p == "??" or p == "??." or p.upper() == "XX":
            buf.append(0x00)
            mask.append(0)
        else:
            v = int(p, 16)
            buf.append(v & 0xFF)
            mask.append(1)
    return (bytes(buf), bytes(mask))

def _find_all(hay: bytes, needle: bytes, mask: bytes) -> List[int]:
    """
    Busca todas las apariciones de 'needle' en haystack, respetando máscara (0 = ignora).
    """
    hits = []
    n = len(needle)
    end = len(hay) - n + 1
    for i in range(end):
        ok = True
        # compara con máscara
        for j in range(n):
            if mask[j] and hay[i+j] != needle[j]:
                ok = False
                break
        if ok:
            hits.append(i)
    return hits

def _apply_op(buf: bytearray, find_hex: str, replace_hex: str, max_hits: Optional[int] = None) -> int:
    """
    Aplica un find/replace (con wildcard). Devuelve cantidad de reemplazos.
    """
    needle, mask = _hex_to_bytes(find_hex)
    repl,   rmask = _hex_to_bytes(replace_hex)

    if len(repl) != len(needle):
        raise ValueError("replace debe tener el mismo largo que find")

    positions = _find_all(bytes(buf), needle, mask)
    if not positions:
        return 0

    count = 0
    for pos in positions:
        # escribe respetando wildcard en replace: si rmask[j]==0, deja byte original
        for j in range(len(needle)):
            if rmask[j]:
                buf[pos+j] = repl[j]
        count += 1
        if max_hits is not None and count >= max_hits:
            break
    return count

def _load_yaml(path: Path) -> Dict:
    import yaml
    return yaml.safe_load(path.read_text(encoding="utf-8"))

def _guess_recipe_paths_for_patch(patch_id: str) -> List[Path]:
    """
    Busca recetas {RECIPES_DIR}/*/{patch_id}.yml en todas las familias.
    """
    out = []
    if not RECIPES_DIR.exists():
        return out
    for fam_dir in RECIPES_DIR.iterdir():
        if fam_dir.is_dir():
            p = fam_dir / f"{patch_id}.yml"
            if p.exists():
                out.append(p)
    return out

def _iter_pack_includes(pack_id: str) -> List[str]:
    """
    Devuelve la lista de patch_ids que componen el pack (desde packs.json).
    """
    try:
        data = json.loads(PACKS_JSON.read_text(encoding="utf-8"))
        for pk in data.get("packs", []):
            if pk.get("id") == pack_id:
                return list(pk.get("includes", []))
    except Exception:
        pass
    return []

# -----------------------------------------------------------------------------------
# API principal
# -----------------------------------------------------------------------------------
def apply_patch(src_path: str, dst_path: str, patch_id: str) -> None:
    """
    Aplica un parche o pack al archivo src_path y lo deja en dst_path.
    - Si patch_id comienza con 'pack_' o si no existe receta para patch_id pero sí existe pack, se aplica pack.
    - Receta YAML formato:
        meta: { name, version, author, notes }
        ops:
          - find: "AA BB CC ?? DD"
            replace: "AA BB EE 11 DD"
            max_hits: 1        # opcional
        checksum:
          type: "none"|"crc32"  # (MVP) "none" por defecto
    """
    src = Path(src_path)
    dst = Path(dst_path)
    data = bytearray(src.read_bytes())

    # ¿Es un pack?
    is_pack = patch_id.startswith("pack:")
    pack_id = patch_id.split(":",1)[1] if is_pack else None
    if not is_pack:
        # Si no hay receta directa pero existe pack con ese id, trátalo como pack
        if not _guess_recipe_paths_for_patch(patch_id):
            includes = _iter_pack_includes(patch_id)
            if includes:
                is_pack = True
                pack_id = patch_id

    if is_pack and pack_id:
        # Aplica cada patch incluído
        includes = _iter_pack_includes(pack_id)
        if not includes:
            raise RuntimeError(f"Pack '{pack_id}' sin 'includes' o no encontrado.")
        for pid in includes:
            data = _apply_recipe_chain(data, pid)
    else:
        data = _apply_recipe_chain(data, patch_id)

    # Escribe salida
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)


def _apply_recipe_chain(buf: bytearray | bytes, patch_id: str) -> bytearray:
    """
    Aplica una receta (si hay más de una familia para el mismo patch_id, usa la primera).
    Si quieres ser más específico, crea la receta en la familia exacta que necesitas.
    """
    buf = bytearray(buf)
    candidates = _guess_recipe_paths_for_patch(patch_id)
    if not candidates:
        # Sin receta → no fallar: no tocar
        # (si prefieres fallar duro, cambia por raise)
        # raise FileNotFoundError(f"No hay receta YAML para '{patch_id}'")
        return buf

    recipe = _load_yaml(candidates[0])

    ops = recipe.get("ops", [])
    total_hits = 0
    for op in ops:
        f = op.get("find", "")
        r = op.get("replace", "")
        mh = op.get("max_hits")
        hits = _apply_op(buf, f, r, max_hits=mh)
        total_hits += hits

    # checksum (MVP)
    csum = recipe.get("checksum", {}) or {}
    ctype = (csum.get("type") or "none").lower()
    if ctype == "crc32":
        import zlib, struct
        # ejemplo simple: escribir CRC32 (LE) en un offset si se especifica
        # { checksum: { type: crc32, offset: 0x1234 } }
        off = csum.get("offset")
        if off is not None:
            cv = zlib.crc32(bytes(buf)) & 0xFFFFFFFF
            crc_le = struct.pack("<I", cv)
            off = int(off)
            if 0 <= off <= len(buf)-4:
                buf[off:off+4] = crc_le
    # (agrega más tipos si los necesitas)

    return buf
