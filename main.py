from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ✅ routers (import directo, sin __init__.py mágicos)
from app.routers.orders import router as orders_router
from app.routers.public_orders import router as public_orders_router
from app.routers.downloads import router as downloads_router
from app.routers.ingest import router as ingest_router
from app.routers.checkout_public import router as checkout_public_router
app.include_router(checkout_public_router)

# -------------------------------------------------------------------
# APP (SOLO UNA)
# -------------------------------------------------------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# ROUTERS
# -------------------------------------------------------------------
app.include_router(orders_router)
app.include_router(public_orders_router)
app.include_router(downloads_router)
app.include_router(ingest_router)

# -------------------------------------------------------------------
# HEALTH
# -------------------------------------------------------------------
@app.get("/health")
def health():
    return {"ok": True}
