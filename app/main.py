from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Depends,
    HTTPException,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from pathlib import Path
import subprocess
import uuid
import json
from datetime import datetime, timedelta

# ---- Auth / DB imports ----
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

# -------------------------------------------------------------------
# Rutas base
#   - Este archivo está en app/main.py
#   - El index.html está en /static a nivel raíz del proyecto
# -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent       # .../app
PROJECT_ROOT = BASE_DIR.parent                   # raíz del repo

STATIC = PROJECT_ROOT / "static"
STORAGE = PROJECT_ROOT / "storage"
STORAGE.mkdir(exist_ok=True)
STATIC.mkdir(exist_ok=True)

# -------------------------------------------------------------------
# DB config (SQLite)
# -------------------------------------------------------------------
DATABASE_URL = f"sqlite:///{PROJECT_ROOT / 'db.sqlite3'}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------------------------------------------------
# Auth / JWT config
# -------------------------------------------------------------------
SECRET_KEY = "ecu-forge-x-super-secret-key"  # TODO: mover a variables de entorno en producción
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas o token expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    return user


# -------------------------------------------------------------------
# App
# -------------------------------------------------------------------
app = FastAPI(
    title="ECU FORGE X",
    version="1.0.0",
)


@app.on_event("startup")
def on_startup():
    # crear tablas DB si no existen
    Base.metadata.create_all(bind=engine)


# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # luego lo limitas a tu dominio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Servir HTML /static/index.html ---
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", response_class=HTMLResponse)
def index():
    index_path = STATIC / "index.html"
    if not index_path.exists():
        return HTMLResponse("<h1>ECU FORGE X</h1><p>Falta static/index.html</p>")
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


# -------------------------------------------------------------------
# ENDPOINTS DE AUTH
# -------------------------------------------------------------------
@app.post("/auth/register")
def register_user(
    email: str,
    password: str,
    full_name: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Registro simple de usuario.
    Más adelante podemos añadir verificación por correo, etc.
    """
    existing = get_user_by_email(db, email)
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un usuario con ese email")

    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        full_name=full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {"id": user.id, "email": user.email, "full_name": user.full_name}


@app.post("/auth/login")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Login estándar OAuth2 (username = email).
    Devuelve un access_token (JWT) para usar en Authorization: Bearer ...
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me")
def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Devuelve los datos del usuario autenticado según el token.
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "created_at": current_user.created_at,
    }


# -------------------------------------------------------------------
# PATCH BIN (generar Bin.MOD real)
#   * De momento NO requiere login para no romper flujo.
#   * Más adelante lo conectamos con pago + token.
# -------------------------------------------------------------------
@app.post("/patch_bin")
async def patch_bin(bin_file: UploadFile = File(...), descriptor: UploadFile = File(...)):

    job_id = str(uuid.uuid4())
    job_dir = STORAGE / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # rutas de entrada
    bin_path = job_dir / f"original_{bin_file.filename}"
    desc_path = job_dir / f"descriptor_{descriptor.filename}"
    out_dir = job_dir / "out"
    out_dir.mkdir(exist_ok=True)

    # guardar archivos subidos
    with open(bin_path, "wb") as f:
        f.write(await bin_file.read())

    with open(desc_path, "wb") as f:
        f.write(await descriptor.read())

    # ejecutar tu CLI patcher usando el módulo app.patcher_cli
    cmd = [
        "python",
        "-m", "app.patcher_cli",
        "--bin", str(bin_path),
        "--descriptor", str(desc_path),
        "--out", str(out_dir),
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            return JSONResponse(
                status_code=500,
                content={
                    "error": "patcher_failed",
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                },
            )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "exception", "detail": str(e)})

    # buscar el Bin.MOD que generó el patcher
    binmods = list(out_dir.glob("*Bin.MOD.zip"))
    if not binmods:
        # si tu patcher genera otro nombre, ajusta este patrón
        return JSONResponse(status_code=500, content={"error": "no_binmod_generated"})

    binmod_path = binmods[0]

    # guardar estado mínimo
    state = {
        "job_id": job_id,
        "bin_file": str(bin_path),
        "descriptor": str(desc_path),
        "binmod": str(binmod_path),
    }
    (job_dir / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")

    # devolver archivo directamente
    return FileResponse(
        path=str(binmod_path),
        filename=binmod_path.name,
        media_type="application/zip",
    )


# -------------------------------------------------------------------
# ANALYZE BIN (Paso 1: mostrar info ECU + opciones de parche)
# -------------------------------------------------------------------
@app.post("/analyze_bin")
async def analyze_bin(bin_file: UploadFile = File(...)):
    """
    Paso 1: analiza el BIN y devuelve información básica de la ECU
    + qué opciones de parche están disponibles.
    Más adelante aquí va tu lógica real de detección.
    """

    filename = bin_file.filename or ""
    contents = await bin_file.read()   # bytes del BIN
    size = len(contents)

    # --- LÓGICA DUMMY SOLO PARA PROBAR FRONT ---
    upper_name = filename.upper()

    if "MED17" in upper_name:
        ecu_type = "MED17.3.9"
        ecu_part_number = "03C906024"
        manufacturer_number = "Bosch 0261"
    else:
        ecu_type = "Desconocida"
        ecu_part_number = "No disponible"
        manufacturer_number = "No disponible"

    available_patches = [
        {
            "id": "dtc_disable",
            "label": "Deshabilitar DTC",
            "description": "Desactivar códigos de avería seleccionados."
        },
        {
            "id": "dp_dpf_egr",
            "label": "Paquete DPF/EGR",
            "description": "Aplicar lógica de anulación para DPF y EGR."
        },
    ]
    # --- FIN LÓGICA DUMMY ---

    return {
        "filename": filename,
        "bin_size": size,
        "ecu_type": ecu_type,
        "ecu_part_number": ecu_part_number,
        "manufacturer_number": manufacturer_number,
        "available_patches": available_patches,
    }
