from __future__ import annotations
import os, uuid, shutil
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
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

ROOT_DIR = Path(__file__).resolve().parent
STATIC_DIR = ROOT_DIR / "static"
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT_DIR / "storage"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

BIN_DIR = DATA_DIR / "uploads_bin"; BIN_DIR.mkdir(exist_ok=True)
MOD_DIR = DATA_DIR / "orders_mod"; MOD_DIR.mkdir(exist_ok=True)
REQ_DIR = DATA_DIR / "requests"; REQ_DIR.mkdir(exist_ok=True)

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

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
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
    user = authenticate_user(db, form.username, form.password)
    if not user:
        raise HTTPException(401, "Email o contraseña incorrectos.")
    token = create_access_token({"sub": str(user.id)})
    return Token(access_token=token)

@app.get("/users/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user

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
        raise HTTPException(400, "Formato de archivo no soportado (usa .bin, .mpc, .org, .e2p).")

    body = await bin_file.read()
    analysis_id = str(uuid.uuid4())
    saved_path = BIN_DIR / f"{analysis_id}_{filename}"
    with open(saved_path, "wb") as f:
        f.write(body)

    up = filename.upper()
    petrol = [
        {"id": "speed_limiter", "label": "Speed Limiter"},
        {"id": "rpm_limit", "label": "RPM Limit Increase"},
        {"id": "dtc_off", "label": "DTC OFF (General)"},
    ]
    diesel = [
        {"id": "dpf_off", "label": "DPF OFF"},
        {"id": "egr_off", "label": "EGR OFF"},
        {"id": "dtc_off", "label": "DTC OFF (General)"},
    ]

    if "MED" in up or "ME" in up or "MG1" in up:
        ecu_type = "Bosch MED/MG1"; ecu_pn = "03C906024"; mf = "Bosch 0261"; patches = petrol
    elif "EDC" in up or "MD1" in up or "MJD" in up or "DCM" in up:
        ecu_type = "Bosch EDC/MD1"; ecu_pn = "03L906018"; mf = "Bosch 0281"; patches = diesel
    else:
        ecu_type = "Desconocida"; ecu_pn = "—"; mf = "—"; patches = []

    return AnalyzeOut(
        analysis_id=analysis_id,
        filename=filename,
        bin_size=len(body),
        ecu_type=ecu_type,
        ecu_part_number=ecu_pn,
        manufacturer_number=mf,
        available_patches=patches,
    )

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
        if o["user_id"] == current_user.id:
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

@app.post("/orders/{order_id}/confirm_payment", response_model=PaymentConfirmOut)
def confirm_payment(order_id: int, current_user: User = Depends(get_current_user)):
    o = orders_db.get(order_id)
    if not o or o["user_id"] != current_user.id:
        raise HTTPException(404, "Orden no encontrada")

    aid = o.get("analysis_id")
    files = list(BIN_DIR.glob(f"{aid}_*")) if aid else []
    out_path = MOD_DIR / f"{stem}_{patch}.mod{ext or '.bin'}"
    MOD_DIR.mkdir(parents=True, exist_ok=True)
    with open(src, "rb") as f_in, open(out_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)

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

class PatchRequestIn(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None
    marca: Optional[str] = None
    modelo: Optional[str] = None
    anio: Optional[str] = None
    motor: Optional[str] = None
    ecu_version: Optional[str] = None
    ecu_type: Optional[str] = None
    ecu_part_number: Optional[str] = None
    manufacturer_number: Optional[str] = None
    analysis_id: Optional[str] = None
    original_filename: Optional[str] = None

@app.post("/patch_requests")
def create_patch_request(req: PatchRequestIn, current_user: User = Depends(get_current_user)):
    import json

    record = req.dict()
    record["id"] = "TCK-" + datetime.utcnow().strftime("%y%m%d") + "-" + uuid.uuid4().hex[:6].upper()
    record["user_id"] = record.get("user_id") or str(current_user.id)
    record["created_at"] = datetime.utcnow().isoformat() + "Z"

    jsonl = REQ_DIR / "patch_requests.jsonl"
    jsonl.parent.mkdir(parents=True, exist_ok=True)

    with open(jsonl, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return {"ok": True, "request_id": record["id"], "sla_hours": 36}
