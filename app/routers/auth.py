# app/routers/auth.py
from fastapi import APIRouter, HTTPException, Request, Header, Depends
from pydantic import BaseModel, EmailStr
from jose import jwt, JWTError
from passlib.context import CryptContext
from datetime import datetime, timedelta
from pathlib import Path
import os, sqlite3

router = APIRouter(prefix="/auth", tags=["auth"])

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-now")
JWT_ALG = "HS256"
JWT_EXPIRE_MIN = int(os.getenv("JWT_EXPIRE_MIN", "10080"))  # 7 días

DATA_DIR = Path(os.getenv("DATA_DIR", "storage"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "auth.db"

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

# -----------------------------
# DB helpers
# -----------------------------
def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def col_exists(con: sqlite3.Connection, table: str, col: str) -> bool:
    cur = con.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    return col in cols

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

    # migración suave: role
    if not col_exists(con, "users", "role"):
        cur.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
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

class AdminCreateUserIn(BaseModel):
    email: EmailStr
    password: str
    role: str = "user"  # "user" o "admin"

# -----------------------------
# JWT helpers
# -----------------------------
def make_token(email: str, role: str = "user") -> str:
    now = datetime.utcnow()
    payload = {
        "sub": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_EXPIRE_MIN)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def parse_bearer(authorization: str | None) -> str:
    auth = authorization or ""
    parts = auth.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, "Missing bearer token")
    return parts[1]

def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    token = parse_bearer(authorization)
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        email = payload.get("sub")
        role = payload.get("role") or "user"
        if not email:
            raise HTTPException(401, "Invalid token")
        return {"email": email, "role": role}
    except JWTError:
        raise HTTPException(401, "Invalid token")

def require_admin(u: dict = Depends(get_current_user)) -> dict:
    if (u.get("role") or "user") != "admin":
        raise HTTPException(403, "Admin only")
    return u

def get_user_row(email: str):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),))
    row = cur.fetchone()
    con.close()
    return row

# -----------------------------
# Endpoints
# -----------------------------
@router.post("/register", response_model=TokenOut)
def register(data: RegisterIn):
    email = data.email.lower().strip()
    if len(data.password) < 6:
        raise HTTPException(400, "Password muy corta (mínimo 6).")

    con = db()
    cur = con.cursor()
    ph = pwd.hash(data.password)

    try:
        cur.execute(
            "INSERT INTO users(email, password_hash, created_at, role) VALUES(?,?,?,?)",
            (email, ph, datetime.utcnow().isoformat(), "user"),
        )
        con.commit()
    except sqlite3.IntegrityError:
        con.close()
        raise HTTPException(409, "Este email ya está registrado.")
    con.close()

    token = make_token(email, "user")
    return {"access_token": token, "token_type": "bearer"}

@router.post("/login", response_model=TokenOut)
def login(data: LoginIn):
    email = data.email.lower().strip()
    row = get_user_row(email)
    if not row:
        raise HTTPException(401, "Credenciales inválidas.")
    if not pwd.verify(data.password, row["password_hash"]):
        raise HTTPException(401, "Credenciales inválidas.")

    role = row["role"] if "role" in row.keys() else "user"
    token = make_token(row["email"], role)
    return {"access_token": token, "token_type": "bearer"}

@router.get("/me")
def me(u: dict = Depends(get_current_user)):
    return {"email": u["email"], "role": u["role"]}

# ---- bootstrap admin (1 vez, por ENV) ----
@router.post("/bootstrap_admin")
def bootstrap_admin():
    admin_email = (os.getenv("ADMIN_EMAIL") or "").lower().strip()
    admin_pass = os.getenv("ADMIN_PASSWORD") or ""
    if not admin_email or len(admin_pass) < 6:
        raise HTTPException(400, "Setea ADMIN_EMAIL y ADMIN_PASSWORD (>=6) en ENV.")

    con = db()
    cur = con.cursor()
    cur.execute("SELECT * FROM users WHERE email=?", (admin_email,))
    row = cur.fetchone()

    if row:
        # si existe, lo elevamos a admin
        cur.execute("UPDATE users SET role='admin' WHERE email=?", (admin_email,))
        con.commit()
        con.close()
        return {"ok": True, "message": "Admin ya existía; rol actualizado a admin."}

    ph = pwd.hash(admin_pass)
    cur.execute(
        "INSERT INTO users(email, password_hash, created_at, role) VALUES(?,?,?,?)",
        (admin_email, ph, datetime.utcnow().isoformat(), "admin"),
    )
    con.commit()
    con.close()
    return {"ok": True, "message": "Admin creado."}

# ---- admin utilities (opcionales pero útiles) ----
@router.get("/admin/users")
def admin_list_users(_: dict = Depends(require_admin)):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT id, email, role, created_at FROM users ORDER BY id DESC")
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return {"users": rows}

@router.post("/admin/users", response_model=TokenOut)
def admin_create_user(data: AdminCreateUserIn, _: dict = Depends(require_admin)):
    email = data.email.lower().strip()
    if len(data.password) < 6:
        raise HTTPException(400, "Password muy corta (mínimo 6).")
    role = (data.role or "user").lower().strip()
    if role not in ("user", "admin"):
        raise HTTPException(400, "role debe ser 'user' o 'admin'.")

    con = db()
    cur = con.cursor()
    ph = pwd.hash(data.password)
    try:
        cur.execute(
            "INSERT INTO users(email, password_hash, created_at, role) VALUES(?,?,?,?)",
            (email, ph, datetime.utcnow().isoformat(), role),
        )
        con.commit()
    except sqlite3.IntegrityError:
        con.close()
        raise HTTPException(409, "Este email ya está registrado.")
    con.close()

    # devuelve token por si quieres loguear directo a ese user
    token = make_token(email, role)
    return {"access_token": token, "token_type": "bearer"}
