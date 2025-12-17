# app/services/patcher.py
from fastapi import HTTPException

def patch_in_padding(data: bytes, needle: bytes, write_ascii: str, max_scan_tail: int = 1048576) -> bytes:
    b = bytearray(data)
    tail_start = max(0, len(b) - max_scan_tail)
    tail = bytes(b[tail_start:])

    idx = tail.find(needle)
    if idx < 0:
        raise HTTPException(status_code=400, detail="No padding region found for demo patch")

    abs_idx = tail_start + idx
    payload = write_ascii.encode("ascii", errors="strict")

    if len(payload) > len(needle):
        raise HTTPException(status_code=400, detail="Payload too long for needle block")

    # sobrescribe dentro del bloque
    b[abs_idx:abs_idx+len(payload)] = payload
    return bytes(b)

def apply_patch(data: bytes, patch_def: dict) -> bytes:
    out = data
    for act in patch_def.get("actions", []):
        t = act.get("type")
        if t == "patch_in_padding":
            needle = bytes.fromhex(act["needle_hex"])
            out = patch_in_padding(
                out,
                needle=needle,
                write_ascii=act["write_ascii"],
                max_scan_tail=int(act.get("max_scan_tail", 1048576))
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action type: {t}")
    return out
