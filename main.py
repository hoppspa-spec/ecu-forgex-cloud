# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# routers
from app.routers import orders
from app.routers import public_orders  # 👈 tu nuevo archivo

app = FastAPI()

# CORS (ajusta si quieres)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ monta routers DESPUÉS de app
app.include_router(orders.router)          # /orders/...
app.include_router(public_orders.router)   # /public/order/...

@app.get("/health")
def health():
    return {"ok": True}
