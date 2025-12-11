# main.py  — ECU FORGE X (Consolidado)

from __future__ import annotations

import os, uuid, shutil, json
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Form
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from pydantic import BaseModel, EmailStr, constr
from jose import jwt, JWTError
from passlib.context import CryptContext

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.exc import IntegrityError

# -------------------------------------------------------------------
# Paths
# -------------------------------------------------------------------
ROOT_DIR   = Path(__file__).resolve().parent
STATIC_DIR = ROOT_DIR / "static"

DATA_DIR = Path(os.getenv("DATA_DIR", ROOT_DIR / "storage"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

BIN_DIR = DATA_DIR / "uploads_bin"; BIN_DIR.mkdir(parents=True, exist_ok=True)
MOD_DIR = DATA_DIR / "orders_mod";  MOD_DIR.mkdir(parents=True, exist_ok=True)
REQ_DIR = DATA_DIR / "requests";    REQ_DIR.mkdir(parents=True, exist_ok=True)

RECIPES_DIR = DATA_DIR / "recipes"; RECIPES_DIR.mkdir(parents=True, exist_ok=True)
PATCHES_DIR = STATIC_DIR / "patches"  # catálogos visibles por el front

# -------------------------------------------------------------------
# App
# -------------------------------------------------------------------
app = FastAPI(title="ECU FORGE X API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")

@app.get("/health")
def health():
    return {"ok": True, "time": datetime.utcnow().isoformat() + "Z"}

# -------------------------------------------------------------------
# DB + Auth
# -------------------------------------------------------------------
DB_PATH = DATA_DIR / "db.sqlite3"
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-please")
ALGORITHM  = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class UserCreate(BaseModel):
    email: EmailStr
    password: constr(min_length=6)
    full_name: Optional[str] = None

class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_pw(p: str) -> str:
    return pwd_context.hash(p)

def verify_pw(p: str, h: str) -> bool:
    return pwd_context.verify(p, h)

def create_access_token(data: dict, minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    to_encode = data.copy()
    to_encode.update({"exp": datetime.utcnow() + timedelta(minutes=minutes)})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    cred_exc = HTTPException(status_code=401, detail="Token inválido", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = int(payload.get("sub", "0"))
    except Exception:
        raise cred_exc
    user = db.get(User, uid)
    if not user:
        raise cred_exc
    return user

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

@app.post("/auth/register", response_model=UserOut)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    user = User(email=user_in.email, hashed_password=hash_pw(user_in.password), full_name=user_in.full_name)
    db.add(user)
    try:
        db.commit(); db.refresh(user)
    except IntegrityError:
        db.rollback(); raise HTTPException(400, "El email ya está registrado.")
    return user

@app.post("/auth/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_pw(form.password, user.hashed_password):
        raise HTTPException(401, "Email o contraseña incorrectos.")
    token = create_access_token({"sub": str(user.id)})
    return Token(access_token=token)

@app.get("/users/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user

# -------------------------------------------------------------------
# Análisis BIN
# -------------------------------------------------------------------
class AnalyzeOut(BaseModel):
    analysis_id: str
    filename: str
    bin_size: int
    ecu_type: str
    ecu_part_number: str
    manufacturer_number: str
    available_patches: list

@app.post("/analyze_bin", response_model=AnalyzeOut)
async def analyze_bin(bin_file: UploadFile = File(...)):
    filename = bin_file.filename or "archivo.bin"
    if not filename.lower().endswith((".bin", ".mpc", ".org", ".e2p", ".101")):
        raise HTTPException(400, "Formato no soportado (usa .bin, .mpc, .org, .e2p, .101).")

    body = await bin_file.read()
    analysis_id = str(uuid.uuid4())
    saved_path = BIN_DIR / f"{analysis_id}_{filename}"
    with open(saved_path, "wb") as f:
        f.write(body)

    up = filename.upper()
    petrol = [
        {"id": "speed_limiter", "label": "Speed Limiter"},
        {"id": "rpm_limit",     "label": "RPM Limit Increase"},
        {"id": "dtc_off",       "label": "DTC OFF (General)"},
    ]
    diesel = [
        {"id": "dpf_off", "label": "DPF OFF"},
        {"id": "egr_off", "label": "EGR OFF"},
        {"id": "dtc_off", "label": "DTC OFF (General)"},
    ]

    if any(k in up for k in ["MED", "MG1", "MEVD", "ME7"]):
        ecu_type, ecu_pn, mf, patches = "Bosch MED/MG1", "03C906024", "Bosch 0261", petrol
    elif any(k in up for k in ["EDC", "MD1", "MJD", "DCM", "SID"]):
        ecu_type, ecu_pn, mf, patches = "Bosch EDC/MD1", "03L906018", "Bosch 0281", diesel
    else:
        ecu_type, ecu_pn, mf, patches = "Desconocida", "—", "—", []

    return AnalyzeOut(
        analysis_id=analysis_id,
        filename=filename,
        bin_size=len(body),
        ecu_type=ecu_type,
        ecu_part_number=ecu_pn,
        manufacturer_number=mf,
        available_patches=patches,
    )

# -------------------------------------------------------------------
# Órdenes (MVP en memoria)
# -------------------------------------------------------------------
orders_db: Dict[int, dict] = {}
_next_id = 1

class OrderCreate(BaseModel):
    analysis_id: Optional[str] = None
    patch_option_id: str

class OrderOut(BaseModel):
    id: int
    checkout_url: str

class PaymentConfirmOut(BaseModel):
    download_url: str

@app.post("/orders", response_model=OrderOut)
def create_order(order: OrderCreate, current_user: User = Depends(get_current_user)):
    global _next_id, orders_db
    oid = _next_id; _next_id += 1
    orders_db[oid] = {
        "id": oid,
        "status": "pending_payment",
        "user_id": current_user.id,
        "patch_option_id": order.patch_option_id,
        "analysis_id": order.analysis_id,
        "mod_file_path": None,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    return OrderOut(id=oid, checkout_url=f"/static/checkout.html?order_id={oid}")

@app.get("/orders/mine")
def my_orders(current_user: User = Depends(get_current_user)):
    out = []
    for o in orders_db.values():
        if o["user_id"] != current_user.id:
            continue
        original = None
        aid = o.get("analysis_id")
        if aid:
            files = list(BIN_DIR.glob(f"{aid}_*"))
            if files:
                name = files[0].name
                parts = name.split("_", 1)
                original = parts[1] if len(parts) == 2 else name
        out.append({
            "id": o["id"],
            "status": o["status"],
            "patch_option_id": o["patch_option_id"],
            "analysis_id": o["analysis_id"],
            "created_at": o["created_at"],
            "original_filename": original,
            "download_ready": bool(o.get("mod_file_path")),
        })
    out.sort(key=lambda x: x["created_at"], reverse=True)
    return {"orders": out}

# helper: aplicar parche con tools/patch_apply.py si existe
def _apply_patch_or_copy(src: Path, dst: Path, patch_id: str):
    """
    Si existe tools/patch_apply.py con función apply_patch(src, dst, patch_id), la usamos.
    Si no, copiamos el archivo (MVP).
    """
    try:
        import importlib.util
        tool_path = ROOT_DIR / "tools" / "patch_apply.py"
        if tool_path.exists():
            spec = importlib.util.spec_from_file_location("patch_apply", str(tool_path))
            mod  = importlib.util.module_from_spec(spec)  # type: ignore
            assert spec and spec.loader
            spec.loader.exec_module(mod)  # type: ignore
            if hasattr(mod, "apply_patch"):
                mod.apply_patch(str(src), str(dst), patch_id)
                return
    except Exception as e:
        print("apply_patch error:", e)
    # fallback
    shutil.copyfile(src, dst)

# --- NUEVO: leer una orden puntual (para checkout) ---
@app.get("/orders/{order_id}")
def get_order(order_id: int, current_user: User = Depends(get_current_user)):
    o = orders_db.get(order_id)
    if not o or o["user_id"] != current_user.id:
        raise HTTPException(404, "Orden no encontrada")
    # también devolvemos nombre original si existe
    original = None
    aid = o.get("analysis_id")
    if aid:
        files = list(BIN_DIR.glob(f"{aid}_*"))
        if files:
            name = files[0].name
            original = name.split("_", 1)[1] if "_" in name else name
    return {**o, "original_filename": original}


# --- REEMPLAZA tu confirm_payment por este ---
@app.post("/orders/{order_id}/confirm_payment", response_model=PaymentConfirmOut)
def confirm_payment(order_id: int, current_user: User = Depends(get_current_user)):
    o = orders_db.get(order_id)
    if not o or o["user_id"] != current_user.id:
        raise HTTPException(404, "Orden no encontrada")

    aid = o.get("analysis_id")
    # localiza el BIN original subido para esta orden
    src_file = None
    if aid:
        candidates = sorted(BIN_DIR.glob(f"{aid}_*"))
        if candidates:
            src_file = candidates[0]

    if not src_file or not src_file.exists():
        raise HTTPException(400, "BIN original no disponible para esta orden")

    patch = o.get("patch_option_id") or "patch"
    # nombre legible basado en el archivo original + patch
    orig_name = src_file.name                               # {analysis_id}_{original}
    original = orig_name.split("_", 1)[1] if "_" in orig_name else orig_name
    base, ext = os.path.splitext(original)
    if not ext:
        ext = ".bin"
    out_name = f"{base}.{patch}.mod{ext}"
    out_path = MOD_DIR / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # MVP: copiamos el BIN y añadimos un tag al final (marca del parche aplicado)
    with open(src_file, "rb") as f_in, open(out_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
        tag = f"\nEFX-MOD:{patch} {datetime.utcnow().isoformat()}Z\n".encode("ascii", "ignore")
        f_out.write(tag)

    o["status"] = "done"
    o["mod_file_path"] = str(out_path)
    return PaymentConfirmOut(download_url=f"/orders/{order_id}/download")

@app.get("/orders/{order_id}/download")
def download_mod(order_id: int, current_user: User = Depends(get_current_user)):
    o = orders_db.get(order_id)
    if not o or o["user_id"] != current_user.id:
        raise HTTPException(404, "Orden no encontrada")
    path = o.get("mod_file_path")
    if not path or not Path(path).exists():
        raise HTTPException(404, "Archivo MOD no disponible")
    fp = Path(path)
    return FileResponse(path=fp, filename=fp.name, media_type="application/octet-stream")

# -------------------------------------------------------------------
# Admin: catálogo y recetas
# -------------------------------------------------------------------
def _ensure_file(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")

def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def _dump_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

class SaveRecipeIn(BaseModel):
    ecu_family: str
    patch_id: str
    label: str
    engines: Optional[List[str]] = None
    compatible_ecu: Optional[List[str]] = None
    price: Optional[int] = 49
    save_catalog: bool = True
    yaml_text: str

@app.post("/admin/save_recipe")
def admin_save_recipe(body: SaveRecipeIn, user: User = Depends(get_current_user)):
    # 1) guardar receta YAML
    fam = (body.ecu_family or "GENERIC").strip()
    rid = (body.patch_id  or "patch").strip()
    recipe_path = RECIPES_DIR / fam / f"{rid}.yml"
    _ensure_file(recipe_path)
    recipe_path.write_text(body.yaml_text, encoding="utf-8")

    # 2) opcional: actualizar catálogo global.json
    saved_in_catalog = False
    if body.save_catalog:
        gpath = PATCHES_DIR / "global.json"
        data  = _load_json(gpath, {"patches": []})
        patches = data.get("patches", [])
        found = next((p for p in patches if p.get("id") == rid), None)
        if found:
            found["label"] = body.label
            if body.engines:        found["engines"] = body.engines
            if body.compatible_ecu: found["compatible_ecu"] = body.compatible_ecu
            if body.price:          found["price"] = body.price
        else:
            patches.append({
                "id": rid,
                "label": body.label,
                "engines": body.engines or [],
                "compatible_ecu": body.compatible_ecu or [],
                "price": body.price or 49
            })
        data["patches"] = patches
        _dump_json(gpath, data)
        saved_in_catalog = True

    return {"ok": True, "recipe_path": str(recipe_path), "catalog_updated": saved_in_catalog}

@app.post("/admin/diff2patch")
async def admin_diff2patch(
    ecu_family: str = Form(...),
    patch_id:  str = Form(...),
    save:      bool = Form(False),
    original_bin: UploadFile = File(...),
    modified_bin: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    import yaml  # PyYAML
    orig = await original_bin.read()
    mod  = await modified_bin.read()
    if len(orig) != len(mod):
        raise HTTPException(400, "Ambos BIN deben tener el MISMO tamaño para este diff simple.")

    # detectar bloques contiguos de diferencia
    ops = []
    i = 0
    while i < len(orig):
        if orig[i] != mod[i]:
            start = i
            while i < len(orig) and orig[i] != mod[i]:
                i += 1
            end = i
            find_hex    = " ".join(f"{b:02X}" for b in orig[start:end])
            replace_hex = " ".join(f"{b:02X}" for b in mod[start:end])
            ops.append({"find": find_hex, "replace": replace_hex})
        else:
            i += 1

    recipe = {
        "meta": {"name": f"{patch_id} ({ecu_family})", "author": user.full_name or user.email,
                 "version": 1, "notes": "Generado automáticamente por diff2patch"},
        "ops": ops,
        "checksum": {"type": "none"}
    }
    yaml_text = yaml.safe_dump(recipe, sort_keys=False, allow_unicode=True)

    saved_to = None
    if save:
        dst = RECIPES_DIR / ecu_family / f"{patch_id}.yml"
        _ensure_file(dst)
        dst.write_text(yaml_text, encoding="utf-8")
        saved_to = str(dst)

    return {"ok": True, "ops_count": len(ops), "yaml": yaml_text, "saved_to": saved_to}

class SaveYamlIn(BaseModel):
    ecu_family: str
    patch_id:   str
    yaml_text:  str

@app.post("/admin/save_yaml")
def admin_save_yaml(body: SaveYamlIn, user: User = Depends(get_current_user)):
    path = RECIPES_DIR / body.ecu_family / f"{body.patch_id}.yml"
    _ensure_file(path)
    path.write_text(body.yaml_text, encoding="utf-8")
    return {"ok": True, "path": str(path)}
