from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.routers.public import router as public_router
from app.routers.admin import router as admin_router
from app.routers.orders import router as orders_router
from app.routers.downloads import router as downloads_router
from app.routers.auth import router as auth_router

# ✅ PRIMERO crear app
app = FastAPI(title="ECU Forge X")

# ✅ Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Static
app.mount("/static", StaticFiles(directory="static"), name="static")

# ✅ DESPUÉS incluir routers
app.include_router(public_router)
app.include_router(admin_router)
app.include_router(orders_router)
app.include_router(downloads_router)
app.include_router(auth_router)

# ✅ Rutas base
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/static/index.html")

@app.get("/admin", include_in_schema=False)
def admin_root():
    return RedirectResponse("/static/admin.html")

@app.get("/healthz")
def healthz():
    return {"ok": True}
