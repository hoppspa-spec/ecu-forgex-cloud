# app/routers/public.py
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from app.services.patch_catalog import list_recipes_for_family

router = APIRouter(prefix="/public", tags=["public"])

@router.get("/recipes/{family}")
def public_list_recipes(family: str, engine: str = Query("auto")):
    """
    Devuelve {"family","engine","recipes":[{id,label,price}]}
    Lee YAMLs desde static/patches/<family>/*.yml
    """
    try:
        data = list_recipes_for_family(family, engine)
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"family": family, "engine": engine, "recipes": [], "error": str(e)}, status_code=200)
