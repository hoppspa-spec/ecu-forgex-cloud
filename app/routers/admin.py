from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/ping")
def ping():
    return {"admin": "pong"}
