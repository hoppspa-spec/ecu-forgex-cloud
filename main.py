from __future__ import annotations

import os, uuid, shutil
# --- extra imports arriba si faltan ---
import json, base64, binascii, re
import yaml  # pip install PyYAML

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
STATIC_DIR = ROOT_DIR / "static"
PATCHES_DIR = STATIC_DIR / "patches"

RECIPES_DIR = DATA_DIR / "recipes"
RECIPES_DIR.mkdir(parents=True, exist_ok=True)

def _ensure_file(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        if path.suffix == ".json":
            path.write_text("{}", encoding="utf-8")
        else:
            path.touch()

def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def _dump_json(path: Path, obj):
    _ensure_file(path)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

# ========== A) Guardar/actualizar entrada de catálogo y receta YAML ==========
class SaveRecipeIn(BaseModel):
    ecu_family: str
    patch_id: str
    label: str
    engines: Optional[list[str]] = None       # ["petrol","diesel"]
    compatible_ecu: Optional[list[str]] = None
    price: Optional[int] = 49
    save_catalog: bool = True
    yaml_text: str

@app.post("/admin/save_recipe")
def admin_save_recipe(body: SaveRecipeIn, user: User = Depends(get_current_user)):
    # 1) guardar receta
    fam = (body.ecu_family or "GENERIC").strip()
    rid = (body.patch_id or "patch").strip()
    recipe_path = RECIPES_DIR / fam / f"{rid}.yml"
    _ensure_file(recipe_path)
    recipe_path.write_text(body.yaml_text, encoding="utf-8")

    # 2) actualizar catálogo (global.json)
    saved_in_catalog = False
    if body.save_catalog:
        gpath = PATCHES_DIR / "global.json"
        _ensure_file(gpath)
        data = _load_json(gpath, {"patches": []})
        patches = data.get("patches", [])
        # busca si existe
        found = next((p for p in patches if p.get("id") == rid), None)
        if found:
            # actualiza
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

# ========== B) Diff → genera YAML de ops ==========
# Sube dos binarios (original y modificado) y generamos ops (find/replace)
from fastapi import Form

@app.post("/admin/diff2patch")
async def admin_diff2patch(
    ecu_family: str = Form(...),
    patch_id: str = Form(...),
    save: bool = Form(False),
    original_bin: UploadFile = File(...),
    modified_bin: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    orig = await original_bin.read()
    mod  = await modified_bin.read()
    if len(orig) != len(mod):
        raise HTTPException(400, "Los archivos deben tener el mismo tamaño para un diff simple (MVP).")

    # detecta bloques contiguos con diferencias
    ops = []
    i = 0
    while i < len(orig):
        if orig[i] != mod[i]:
            start = i
            while i < len(orig) and orig[i] != mod[i]:
                i += 1
            end = i  # [start,end)
            # construye strings hex "AA BB ..."
            find_hex = " ".join(f"{b:02X}" for b in orig[start:end])
            replace_hex = " ".join(f"{b:02X}" for b in mod[start:end])
            ops.append({"find": find_hex, "replace": replace_hex})
        else:
            i += 1

    recipe = {
        "meta": {
            "name": f"{patch_id} ({ecu_family})",
            "author": user.full_name or user.email,
            "version": 1,
            "notes": "Generado automáticamente por diff2patch"
        },
        "ops": ops,
        "checksum": {"type": "none"}
    }
    yaml_text = yaml.safe_dump(recipe, sort_keys=False, allow_unicode=True)

    recipe_path = None
    if save:
        dst = RECIPES_DIR / ecu_family / f"{patch_id}.yml"
        _ensure_file(dst)
        dst.write_text(yaml_text, encoding="utf-8")
        recipe_path = str(dst)

    return {"ok": True, "ops_count": len(ops), "yaml": yaml_text, "saved_to": recipe_path}

# ========== C) Guardar receta suelta (generada por editor HEX del front) ==========
class SaveYamlIn(BaseModel):
    ecu_family: str
    patch_id: str
    yaml_text: str

@app.post("/admin/save_yaml")
def admin_save_yaml(body: SaveYamlIn, user: User = Depends(get_current_user)):
    path = RECIPES_DIR / body.ecu_family / f"{body.patch_id}.yml"
    _ensure_file(path)
    path.write_text(body.yaml_text, encoding="utf-8")
    return {"ok": True, "path": str(path)}

from typing import Optional, Dict
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from pydantic import BaseModel, EmailStr, constr
from jose import jwt
from passlib.context import CryptContext

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.exc import IntegrityError

# -------------------------------------------------------------------
# Paths y carpetas
# -------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent
STATIC_DIR = ROOT_DIR / "static"
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT_DIR / "storage"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

BIN_DIR = DATA_DIR / "uploads_bin"; BIN_DIR.mkdir(exist_ok=True)
MOD_DIR = DATA_DIR / "orders_mod"; MOD_DIR.mkdir(exist_ok=True)
REQ_DIR = DATA_DIR / "requests"; REQ_DIR.mkdir(exist_ok=True)

# -------------------------------------------------------------------
# App
# -------------------------------------------------------------------
app = FastAPI(title="ECU FORGE X API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
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

def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_pw(password, user.hashed_password):
        return None
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
    user = authenticate_user(db, form.username, form.password)
    if not user:
        raise HTTPException(401, "Email o contraseña incorrectos.")
    token = create_access_token({"sub": str(user.id)})
    return Token(access_token=token)

@app.get("/users/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user := lambda token=Depends(oauth2_scheme), db=Depends(get_db): None)):
    # pequeño wrapper para no duplicar código de verificación
    try:
        payload = jwt.decode(get_current_user.__defaults__[0], SECRET_KEY, algorithms=[ALGORITHM])  # type: ignore
        uid = int(payload.get("sub", "0"))
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")
    user = db.get(User, uid)  # type: ignore
    if not user:
        raise HTTPException(status_code=401, detail="Token inválido")
    return user
