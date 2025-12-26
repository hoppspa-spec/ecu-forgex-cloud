# app/services/storage.py
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

# Render Disk mount
DATA_DIR = Path(os.getenv("DATA_DIR", "/storage/efx"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

TMP_DIR = DATA_DIR / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

ORDERS_DIR = DATA_DIR / "orders"
ORDERS_DIR.mkdir(parents=True, exist_ok=True)


def order_dir(order_id: str) -> Path:
    d = ORDERS_DIR / order_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def order_json_path(order_id: str) -> Path:
    return order_dir(order_id) / "order.json"


def save_order(order_id: str, data: dict) -> None:
    p = order_json_path(order_id)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_order(order_id: str) -> Optional[dict]:
    p = order_json_path(order_id)
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def now_iso() -> str:
    return datetime.utcnow().isoformat()
