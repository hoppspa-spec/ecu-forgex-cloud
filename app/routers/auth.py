# app/routers/auth.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from jose import jwt, JWTError
from passlib.context import CryptContext
from datetime import datetime, timedelta
from pathlib import Path
import os, sqlite3

router = APIRouter(prefix="/auth", tags=["auth"])

# -----------------------------
# Config
# -----------------------------
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-now")  # 👈 ponlo en Render ENV
JWT_ALG = "HS256"
JWT_EXPIRE_MIN = int(os.getenv("JWT_EXPIRE_MIN", "10080"))  # 7 días

DATA_DIR = Path(os.getenv("DATA_DIR", "storage"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "auth.db"

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    cur = con.cursor()
    cur.execute("""
      CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
      )
    """)
    con.commit()
    con.close()

init_db()

# -----------------------------
# Models
# -----------------------------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

# -----------------------------
# JWT helpers
# -----------------------------
def make_token(email: str) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_EXPIRE_MIN)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def get_current_email(authorization: str | None = None) -> str:
    # FastAPI no inyecta header aquí directo si no usamos Header(), lo resolvemos en /me.
    raise NotImplementedError

# -----------------------------
# Endpoints
# -----------------------------
@router.post("/register")
def register(data: RegisterIn):
    if len(data.password) < 6:
        raise HTTPException(400, "Password muy corta (mínimo 6).")

    con = db()
    cur = con.cursor()

    ph = pwd.hash(data.password)
    try:
        cur.execute(
            "INSERT INTO users(email, password_hash, created_at) VALUES(?,?,?)",
            (data.email.lower().strip(), ph, datetime.utcnow().isoformat()),
        )
        con.commit()
    except sqlite3.IntegrityError:
        con.close()
        raise HTTPException(409, "Este email ya está registrado.")
    con.close()

    # opcional: loguear directo después de registrar
    token = make_token(data.email.lower().strip())
    return {"access_token": token, "token_type": "bearer"}

@router.post("/login", response_model=TokenOut)
def login(data: LoginIn):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (data.email.lower().strip(),))
    row = cur.fetchone()
    con.close()

    if not row:
        raise HTTPException(401, "Credenciales inválidas.")

    if not pwd.verify(data.password, row["password_hash"]):
        raise HTTPException(401, "Credenciales inválidas.")

    token = make_token(row["email"])
    return {"access_token": token, "token_type": "bearer"}

from fastapi import Request

@router.get("/me")
def me(request: Request):
    auth = request.headers.get("authorization") or ""
    parts = auth.split()

    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, "Missing bearer token")

    token = parts[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        email = payload.get("sub")
        if not email:
            raise HTTPException(401, "Invalid token")
        return {"email": email}
    except JWTError:
        raise HTTPException(401, "Invalid token")


