from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import upload
from app.routers import ingest

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)     # GET /upload
app.include_router(ingest.router)     # POST /api/ingest-multipart + GET /api/public/order/...

@app.get("/health")
def health():
    return {"ok": True}
