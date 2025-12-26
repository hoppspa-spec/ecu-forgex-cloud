from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from app.services.storage import save_order

# ✅ importa routers DIRECTO (no desde app.routers import algo)
from app.routers.orders import router as orders_router
from app.routers.public_orders import router as public_orders_router
from app.routers.downloads import router as downloads_router  # ojo: archivo downloads.py

# (si tu router de upload/ingest está en otro archivo, lo sumamos acá)
# from app.routers.upload import router as upload_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(orders_router)
app.include_router(public_orders_router)
app.include_router(downloads_router)
# app.include_router(upload_router)

@app.get("/health")
def health():
    return {"ok": True}
