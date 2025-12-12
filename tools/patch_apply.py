# tools/patch_apply.py
# Motor PRO: aplica recetas YAML por patrones (hex + numéricos) con selectores por ECU/SW/CVN.
from __future__ import annotations
import os, re, struct, glob, json
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import yaml  # PyYAML
except Exception as e:
    raise RuntimeError("PyYAML requerido. Agrega 'PyYAML' a requirements.txt") from e

ROOT = Path(__file__).resolve().parents[1]   # repo root
RECIPES_DIR = ROOT / "store" / "recipes"

# -------------------------------
# Utils
# -------------------------------
def _read_bytes(path: Path) -> bytearray:
    with open(path, "rb") as f:
        return bytearray(f.read())

def _write_bytes(path: Path, data: bytes) -> None:
    with open(path, "wb") as f:
        f.write(data)

def _hex_to_bytes(s: str) -> bytes:
    s = re.sub(r"[^0-9A-Fa-f]", " ", s or "")
    parts = [p for p in s.split() if p]
    return bytes(int(p, 16) for p in parts)

def _pack_number(kind: str, value: float, endian: str="le") -> bytes:
    """Empaqueta número según tipo/endian."""
    e = "<" if endian.lower().startswith("le") else ">"
    k = kind.lower()
    if   k == "u8":  return struct.pack("B", int(value) & 0xFF)
    elif k == "i8":  return struct.pack("b", int(value))
    elif k == "u16": return struct.pack(e+"H", int(value) & 0xFFFF)
    elif k == "i16": return struct.pack(e+"h", int(value))
    elif k == "u32": return struct.pack(e+"I", int(value) & 0xFFFFFFFF)
    elif k == "i32": return struct.pack(e+"i", int(value))
    elif k == "f32": return struct.pack(e+"f", float(value))
    elif k == "f64": return struct.pack(e+"d", float(value))
    else:
        raise ValueError(f"tipo numérico no soportado: {kind}")

def _iter_number_matches(buf: bytes, kind: str, target: float, *, endian="le", tol=0, align=None, scale=None) -> List[int]:
    """
    Busca ocurrencias del número (con escala y tolerancia).
    scale: si se define, comparamos pack(value*scale)
    tol:   para floats: diferencia absoluta aceptada; para enteros: ±tol
    align: si se define, solo índices % align == 0
    """
    k = kind.lower()
    size_map = {"u8":1,"i8":1,"u16":2,"i16":2,"u32":4,"i32":4,"f32":4,"f64":8}
    sz = size_map.get(k)
    if not sz: raise ValueError(f"tipo no soportado: {kind}")
    e = "<" if endian.lower().startswith("le") else ">"

    # valor esperado
    if scale not in (None, 1):
        target_eff = target * float(scale)
    else:
        target_eff = target

    hits = []
    i = 0
    limit = len(buf) - sz
    while i <= limit:
        if align and (i % align) != 0:
            i += 1; continue
        chunk = buf[i:i+sz]
        try:
            if   k == "u8":  val = struct.unpack("B", chunk)[0]
            elif k == "i8":  val = struct.unpack("b", chunk)[0]
            elif k == "u16": val = struct.unpack(e+"H", chunk)[0]
            elif k == "i16": val = struct.unpack(e+"h", chunk)[0]
            elif k == "u32": val = struct.unpack(e+"I", chunk)[0]
            elif k == "i32": val = struct.unpack(e+"i", chunk)[0]
            elif k == "f32": val = struct.unpack(e+"f", chunk)[0]
            elif k == "f64": val = struct.unpack(e+"d", chunk)[0]
        except struct.error:
            i += 1; continue

        ok = False
        if k.startswith(("f32","f64")):
            ok = abs(float(val) - float(target_eff)) <= float(tol or 0)
        else:
            ok = (int(val) >= int(target_eff - (tol or 0)) and int(val) <= int(target_eff + (tol or 0)))

        if ok:
            hits.append(i)
        i += 1
    return hits

def _apply_hex(buf: bytearray, find_b: bytes, repl_b: bytes, *, expect: Optional[int]=None) -> int:
    cnt = 0
    i = 0
    L = len(find_b)
    if L == 0: return 0
    while True:
        j = buf.find(find_b, i)
        if j < 0: break
        buf[j:j+L] = repl_b
        cnt += 1
        i = j + len(repl_b)  # continuar luego del reemplazo
    if expect is not None and cnt < expect:
        raise RuntimeError(f"find_hex esperaba >= {expect} match(es) y encontró {cnt}")
    return cnt

def _apply_number(buf: bytearray, op: Dict[str, Any]) -> int:
    kind   = op["kind"]               # u16,u32,f32,f64...
    value  = float(op["value"])
    endian = op.get("endian","le")
    tol    = float(op.get("tol", 0))
    align  = op.get("align")          # ej. 2 o 4 si sabes que está alineado
    scale  = op.get("scale")          # ej. km/h→unidad interna
    expect = op.get("expect")         # mínimo de aciertos esperados
    replace_value = float(op.get("replace_value", value))
    replace_scale = op.get("replace_scale", scale)

    hits = _iter_number_matches(buf, kind, value, endian=endian, tol=tol, align=align, scale=scale)
    if not hits and expect:
        raise RuntimeError(f"value_find {kind} no encontró coincidencias (expect>0). value={value}, tol={tol}")

    repl_bytes = _pack_number(kind, replace_value * (float(replace_scale) if replace_scale not in (None,1) else 1), endian=endian)
    for pos in hits:
        buf[pos:pos+len(repl_bytes)] = repl_bytes
    return len(hits)

def _matches_selectors(buf: bytes, sel: Dict[str, Any]) -> bool:
    """Evalúa selectores: sw_contains[], cvn_in[], size_between[], regex_any[]"""
    if not sel: return True
    # SW / CVN / size pueden venir de otra capa. Aquí hacemos heurística con regex/bytes.
    size_between = sel.get("size_between")
    if size_between:
        lo, hi = size_between
        if not (int(lo) <= len(buf) <= int(hi)): return False

    regex_any = sel.get("regex_any", [])
    for pat in regex_any:
        if not re.search(pat, buf, flags=re.DOTALL):
            return False

    # Permite matches por "markers" en ASCII (útil cuando el SW imprime cadenas)
    ascii_contains = sel.get("ascii_contains", [])
    view = None
    if ascii_contains:
        try:
            view = buf.decode("latin-1", "ignore")
        except Exception:
            view = ""
        for s in ascii_contains:
            if s not in view:
                return False

    return True

# -------------------------------
# Carga y aplicación
# -------------------------------
def _load_family_recipes(family: str) -> List[Dict[str, Any]]:
    paths = sorted(glob.glob(str((RECIPES_DIR / family).glob("*.yml"))))
    out = []
    for p in paths:
        try:
            data = yaml.safe_load(Path(p).read_text(encoding="utf-8")) or {}
            data["_path"] = p
            out.append(data)
        except Exception as e:
            raise RuntimeError(f"Error cargando receta {p}: {e}")
    return out

def _detect_family_from_name(name: str) -> Optional[str]:
    up = name.upper()
    for fam in [d.name for d in RECIPES_DIR.iterdir() if d.is_dir()]:
        if fam.upper() in up:
            return fam
    # heurística simple
    if "MEVD" in up: return "MEVD17"
    if "MED17" in up: return "MED17"
    if "MD1" in up: return "MD1"
    if "EDC17" in up: return "EDC17"
    return None

def apply_patch(src_path: str, dst_path: str, patch_id: str) -> None:
    """
    Aplica el 'patch_id' buscando recetas compatibles por familia + selectores.
    - Si hay varias recetas compatibles, aplica TODAS sus 'ops' (orden archivo).
    - Si ninguna receta match → error (quedará fallback en la capa superior si la implementaste).
    """
    src = Path(src_path); dst = Path(dst_path)
    buf = _read_bytes(src)

    # 1) detectar familia por nombre de archivo o heurística
    family = _detect_family_from_name(src.name) or _detect_family_from_name(patch_id) or ""
    if not family:
        raise RuntimeError("No se pudo inferir familia ECU (usa nombre que contenga MEVD17/EDC17/MD1, etc.)")

    # 2) cargar recetas de la familia
    recipes = _load_family_recipes(family)
    if not recipes:
        raise RuntimeError(f"Sin recetas para familia {family}")

    total_changes = 0
    compatible = 0

    for rec in recipes:
        meta = rec.get("meta", {})
        rid  = meta.get("id") or Path(rec.get("_path","")).stem

        # filtro por patch_id
        targets = meta.get("patch_ids") or [meta.get("patch_id"), rid]
        targets = [t for t in targets if t]
        if targets and patch_id not in targets:
            continue

        # selectores
        if not _matches_selectors(bytes(buf), rec.get("selectors", {})):
            continue

        # aplicar ops
        ops = rec.get("ops", [])
        changed = 0
        for op in ops:
            if "find_hex" in op:
                find_b = _hex_to_bytes(op["find_hex"])
                repl_b = _hex_to_bytes(op.get("replace_hex", ""))
                exp    = op.get("expect")
                changed += _apply_hex(buf, find_b, repl_b, expect=exp)
            elif "value_find" in op:
                vf = op["value_find"]
                # vf: {kind, value, endian?, tol?, align?, scale?, replace_value?, replace_scale?, expect?}
                changed += _apply_number(buf, vf)
            else:
                raise RuntimeError(f"Operación no soportada en {rec.get('_path')}: {op}")

        if changed > 0:
            compatible += 1
            total_changes += changed

    if compatible == 0:
        raise RuntimeError(f"No hubo recetas compatibles para '{patch_id}' en familia {family}")

    _write_bytes(dst, bytes(buf))
