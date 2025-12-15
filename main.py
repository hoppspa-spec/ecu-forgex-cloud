# src/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importa routers *después* de crear app o usa una factory;
# aquí usamos factory para evitar cualquier orden raro.
from app.routers import public as public_router
from app.routers import admin as admin_router
from app.routers import auth as auth_router
from app.routers import orders as orders_router

def create_app() -> FastAPI:
    app = FastAPI(title="ECU Forge X", version="0.1.0")

    # CORS (ajusta orígenes si quieres)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Incluye routers aquí, con prefijos si aplica
    app.include_router(public_router.router, prefix="")
    app.include_router(auth_router.router,   prefix="/auth")
    app.include_router(admin_router.router,  prefix="/admin")
    app.include_router(orders_router.router, prefix="")

    @app.get("/health")
    def health():
        return {"ok": True}

    return app

# instancia que uvicorn/render usará -> "app.main:app"
app = create_app()
