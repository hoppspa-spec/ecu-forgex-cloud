from pathlib import Path
import json, re
from typing import Optional, Dict, Any

PATCH_ROOT = Path("static/patches")

def list_families() -> list[dict]:
    out = []
    for d in PATCH_ROOT.iterdir():
        if not d.is_dir(): continue
        meta = d / "meta.json"
        label = d.name
        engine = None
        if meta.exists():
            m = json.loads(meta.read_text())
            label = m.get("label", label)
            engine = m.get("engine_default")
        out.append({"family": d.name, "label": label, "engine_default": engine})
    return out

def detect_family(ecu_type: str|None, filename: str|None, bin_text: str|None) -> Optional[str]:
    # 1) por ecu_type
    for d in PATCH_ROOT.iterdir():
        if not d.is_dir(): continue
        if ecu_type and d.name.upper() in ecu_type.upper():
            return d.name
    # 2) por detectors.json
    for d in PATCH_ROOT.iterdir():
        if not d.is_dir(): continue
        det = d / "detectors.json"
        if not det.exists(): continue
        arr = json.loads(det.read_text())
        for r in arr:
            if r.get("pn") and bin_text and r["pn"] in bin_text:
                return d.name
            if r.get("sw") and bin_text and r["sw"] in bin_text:
                return d.name
    # 3) heurística por nombre archivo
    src = (filename or "").upper()
    for key in ["EDC","MED","MG1","MD1","DCM","SID","MEVD","ME7"]:
        if key in src:
            # si hay carpeta con ese prefijo, úsala
            for d in PATCH_ROOT.iterdir():
                if d.is_dir() and key in d.name.upper():
                    return d.name
    return None

def list_patches_for_family(family: str, brand: str|None=None) -> list[dict]:
    fam_dir = PATCH_ROOT / family.upper()
    if not fam_dir.exists(): return []
    meta_path = fam_dir / "meta.json"
    overrides: Dict[str, Any] = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        overrides = meta.get("overrides", {})
    items = []
    for p in fam_dir.iterdir():
        if p.suffix in (".yml",".bsdiff"):
            pid = p.stem
            label = pid.replace("_"," ").upper()
            engine = None
            price = None
            # si es YAML, lee label/engine
            if p.suffix == ".yml":
                try:
                    import yaml
                    r = yaml.safe_load(p.read_text(encoding="utf-8"))
                    label = r.get("label", label)
                    engine = r.get("engine")
                except: pass
            # overrides por marca
            if brand and brand in overrides:
                o = overrides[brand]
                if "rename" in o and pid in o["rename"]:
                    label = o["rename"][pid]
                if "price" in o and pid in o["price"]:
                    price = o["price"][pid]
            items.append({"id": pid, "label": label, "engine": engine, "price": price})
    return sorted(items, key=lambda x: x["label"])
