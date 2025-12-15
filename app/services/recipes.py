# Hace a app/routers un paquete de Python
# No exporta nada; importamos por módulo (public/admin).
# app/services/recipes.py
from pathlib import Path
import json
import yaml

ROOT = Path(__file__).resolve().parents[2]
RECIPES_DIR = ROOT / "store" / "recipes"

def list_families():
    if not RECIPES_DIR.exists():
        return []
    return sorted([p.name for p in RECIPES_DIR.iterdir() if p.is_dir() and not p.name.startswith("_")])

def load_family_meta(family: str):
    meta_path = RECIPES_DIR / family / "meta.json"
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def list_family_recipes(family: str):
    fam_dir = RECIPES_DIR / family
    out = []
    if not fam_dir.exists():
        return out
    for yml in sorted(fam_dir.glob("*.yml")):
        recipe_id = yml.stem
        label = recipe_id.replace("_", " ").upper()
        out.append({
            "id": recipe_id,
            "label": label,
            "path": str(yml.relative_to(ROOT)),
        })
    return out

def get_family_catalog(family: str):
    fam = family.strip()
    if not fam:
        return {"family": None, "recipes": [], "meta": {}}
    meta = load_family_meta(fam)
    recipes = list_family_recipes(fam)

    # aplica overrides de meta.json (label, price, active, engines, etc.)
    overrides = meta.get("recipes", {})
    for r in recipes:
        ov = overrides.get(r["id"], {})
        if "label" in ov:   r["label"] = ov["label"]
        if "price" in ov:   r["price"] = ov["price"]
        if "active" in ov:  r["active"] = bool(ov["active"])
        if "engines" in ov: r["engines"] = [str(e).lower() for e in ov["engines"]]

    # por defecto activos
    for r in recipes:
        r.setdefault("active", True)

    return {
        "family": fam,
        "meta": {k: v for k, v in meta.items() if k != "recipes"},
        "recipes": recipes,
    }
