from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

# Healthcheck para Render
@app.get("/healthz")
def healthz():
    return {"ok": True}
