from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/ping")
def admin_ping():
    return {"admin": "pong"}
