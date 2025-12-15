# app/routers/public.py
from fastapi import APIRouter, HTTPException, Query
from app.services.recipes import list_families, get_family_catalog

router = APIRouter(prefix="/public", tags=["public"])

@router.get("/families")
def families():
    return {"families": list_families()}

@router.get("/recipes/{family}")
def recipes_by_family(family: str, engine: str | None = Query(default=None, description="petrol|diesel|auto")):
    cat = get_family_catalog(family)
    fam = cat.get("family")
    if not fam:
        raise HTTPException(status_code=404, detail="Family not found")

    eng = (engine or "auto").lower().strip()
    items = cat.get("recipes", [])

    # filtra por engine si corresponde
    if eng in ("petrol", "diesel"):
        def _ok(r):
            engines = r.get("engines")
            if not engines:
                return True  # si no especifica, se muestra
            return eng in engines
        items = [r for r in items if _ok(r)]

    # sólo activos
    items = [r for r in items if r.get("active", True)]

    return {
        "family": fam,
        "recipes": items,
        "meta": cat.get("meta", {})
    }
