from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles   # ⬅️ nuevo

from app.routers.public import router as public_router
from app.routers.admin  import router as admin_router

app = FastAPI(title="ECU Forge X")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ⬇️ monta archivos estáticos (sirve /static/** desde la carpeta ./static)
app.mount("/static", StaticFiles(directory="static"), name="static")  # ⬅️ nuevo

# Routers
app.include_router(public_router)
app.include_router(admin_router)

# Redirecciones cómodas
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/static/index.html")

@app.get("/admin", include_in_schema=False)
def admin_root():
    return RedirectResponse("/static/admin.html")

# Health
@app.get("/healthz")
def healthz():
    return {"ok": True}


# 🔴 Importa los routers por archivo, NO desde el paquete vacío
from app.routers.public import router as public_router
from app.routers.admin import router as admin_router

app = FastAPI(title="ECU Forge X")

# CORS básico
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Monta routers
app.include_router(public_router)
app.include_router(admin_router)
from fastapi.responses import RedirectResponse

# Redirección a front y admin
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/static/index.html")

@app.get("/admin", include_in_schema=False)
def admin_root():
    return RedirectResponse(url="/static/admin.html")

# Healthcheck para Render
@app.get("/healthz")
def healthz():
    return {"ok": True}
