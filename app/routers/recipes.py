# app/routers/recipes.py
from fastapi import APIRouter, HTTPException
import json, os

router = APIRouter(prefix="/public/recipes", tags=["recipes"])

BASE = os.path.join(os.path.dirname(__file__), "..", "recipes")

def load_family(family: str):
    path = os.path.join(BASE, f"{family}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Family not found")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@router.get("/{family}")
def get_recipes(family: str, engine: str = "auto"):
    d = load_family(family)
    patches = d.get("patches", [])
    return {"family": family, "engine": d.get("engine"), "recipes": patches}
