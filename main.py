from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.routers.public import router as public_router
from app.routers.admin import router as admin_router

app = FastAPI(title="ECU Forge X")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sirve archivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routers
app.include_router(public_router)
app.include_router(admin_router)

# Redirecciones a frontend y admin
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/static/index.html")

@app.get("/admin", include_in_schema=False)
def admin_root():
    return RedirectResponse(url="/static/admin.html")

# Healthcheck (Render usa esto)
@app.get("/healthz")
def healthz():
    return {"ok": True}

