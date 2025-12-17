from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import uuid, os, json, tempfile
from app.routers.public import ANALYSIS_DB
from app.services.patcher import apply_patch

router = APIRouter(prefix="/orders", tags=["orders"])

class OrderCreate(BaseModel):
    analysis_id: str
    patch_option_id: str

ORDERS_DB = {}

RECIPES_BASE = os.path.join(os.path.dirname(__file__), "..", "recipes")

def load_family(family: str):
    path = os.path.join(RECIPES_BASE, f"{family}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Family recipe not found")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def find_patch(family_json: dict, patch_id: str):
    for p in family_json.get("patches", []):
        if p.get("id") == patch_id:
            return p
    return None

@router.post("")
def create_order(data: OrderCreate):
    a = ANALYSIS_DB.get(data.analysis_id)
    if not a:
        raise HTTPException(status_code=404, detail="analysis_id not found")

    family = a["ecu_type"]
    fam = load_family(family)
    patch = find_patch(fam, data.patch_option_id)
    if not patch:
        raise HTTPException(status_code=404, detail="patch_option_id not found for this family")

    # reglas simples
    size = a["bin_size"]
    rules = patch.get("rules", {})
    if rules.get("min_size") and size < int(rules["min_size"]):
        raise HTTPException(status_code=400, detail="BIN too small for this patch")
    if rules.get("max_size") and size > int(rules["max_size"]):
        raise HTTPException(status_code=400, detail="BIN too large for this patch")

    # aplicar patch real
    mod_bytes = apply_patch(a["bytes"], patch)

    # guardar mod temporal
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mod.bin")
    tmp.write(mod_bytes)
    tmp.close()

    order_id = str(uuid.uuid4())
    order = {
        "id": order_id,
        "analysis_id": data.analysis_id,
        "patch_option_id": data.patch_option_id,
        "status": "done",                 # demo: queda listo
        "download_ready": True,
        "mod_file_path": tmp.name,
        "original_filename": a["filename"],
        "checkout_url": f"/static/checkout.html?order_id={order_id}"
    }
    ORDERS_DB[order_id] = order
    return order

@router.get("/{order_id}")
def get_order(order_id: str):
    o = ORDERS_DB.get(order_id)
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    return o
