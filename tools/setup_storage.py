# tools/setup_storage.py
from __future__ import annotations
from pathlib import Path
import json
import shutil

DEFAULT_GLOBAL = {
    "patches": [
        # ejemplo demo; puedes borrar/editar luego
        {"id": "dpf_off", "label": "DPF OFF", "engines": ["diesel"], "compatible_ecu": ["EDC17","MD1"], "price": 49},
        {"id": "speed_limiter", "label": "Speed Limiter OFF", "engines": ["petrol"], "compatible_ecu": ["MED17","MG1"], "price": 39}
    ]
}

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def write_json_if_missing(path: Path, obj) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def copy_if_missing(src: Path, dst: Path) -> None:
    if src.exists() and not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)

def autoinit(data_dir: Path, static_dir: Path) -> None:
    """
    Prepara estructura persistente en data_dir y garantiza catálogos en static_dir.
    Llamar en startup.
    """
    # Estructura runtime/persistente
    uploads = data_dir / "uploads_bin"
    orders  = data_dir / "orders_mod"
    reqs    = data_dir / "requests"
    recipes = data_dir / "recipes"

    for d in (data_dir, uploads, orders, reqs, recipes):
        ensure_dir(d)

    # Asegurar .gitkeep/.gitignore opcional
    (recipes / ".gitignore").write_text("*\n!.gitignore\n", encoding="utf-8")

    # Catálogo visible por el front
    patches_dir = static_dir / "patches"
    ensure_dir(patches_dir)

    # global.json: si no existe, crear con contenido por defecto
    write_json_if_missing(patches_dir / "global.json", DEFAULT_GLOBAL)

    # carpetas opcionales para overrides
    ensure_dir(patches_dir / "brand")
    # packs.json de ejemplo
    write_json_if_missing(patches_dir / "packs.json", {"packs": []})
