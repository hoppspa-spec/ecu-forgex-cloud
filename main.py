from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.orders import router as orders_router
from app.routers.public_orders import router as public_orders_router
from app.routers.downloads import router as downloads_router
from app.routers.ingest import router as ingest_router   # 👈 ESTE ES CLAVE

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
app.include_router(ingest_router)   # 👈 SI FALTA ESTO, TODO FALLA

@app.get("/health")
def health():
    return {"ok": True}


app.include_router(orders_router)
app.include_router(public_orders_router)
app.include_router(downloads_router)
# app.include_router(upload_router)

@app.get("/health")
def health():
    return {"ok": True}
