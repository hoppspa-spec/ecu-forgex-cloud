from fastapi import APIRouter, HTTPException

router = APIRouter(
    prefix="/public/order",
    tags=["public-orders"]
)

# mock temporal (después lo conectamos a DB real)
PUBLIC_ORDERS_DB = {}

@router.get("/{order_id}")
def get_public_order(order_id: str):
    order = PUBLIC_ORDERS_DB.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
