# app/services/patch_catalog.py
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml

PATCHES_ROOT = Path("static/patches")

def _to_usd(price_like: Any) -> Optional[float]:
    if price_like is None:
        return None
    if isinstance(price_like, (int, float)):
        return float(price_like)
    if isinstance(price_like, dict):
        if "USD" in price_like and price_like["USD"] is not None:
            try:
                return float(price_like["USD"])
            except Exception:
                return None
    return None

def list_recipes_for_family(family: str, engine: str = "auto") -> Dict[str, Any]:
    """
    Lee YAMLs en static/patches/<family>/*.yml y arma un catálogo.
    Filtra por 'engines' si el YAML lo trae.
    """
    folder = PATCHES_ROOT / family
    out: List[Dict[str, Any]] = []

    if not folder.exists() or not folder.is_dir():
        return {"family": family, "engine": engine, "recipes": []}

    for yml in sorted(folder.glob("*.yml")):
        try:
            with yml.open("r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
        except Exception:
            continue

        rid = str(data.get("id") or yml.stem)
        label = str(data.get("label") or rid)
        price = _to_usd(data.get("price"))
        engines = [str(e).lower() for e in (data.get("engines") or [])]
        compat = [str(c).upper() for c in (data.get("compatible_ecu") or [])]

        # Filtrado por engine si el YAML declara engines
        if engines:
            want = (engine or "auto").lower()
            if want != "auto" and want not in engines:
                continue

        # (Opcional) Filtrado por familia si el YAML declara compatible_ecu
        if compat and family.upper() not in compat:
            continue

        out.append({
            "id": rid,
            "label": label,
            "price": price,
        })

    return {"family": family, "engine": engine, "recipes": out}
