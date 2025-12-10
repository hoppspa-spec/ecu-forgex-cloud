# tools/patch_apply.py
from __future__ import annotations
import argparse, sys, re
from pathlib import Path
from typing import List, Tuple

def _pattern_to_regex(hex_str: str) -> re.Pattern[bytes]:
    parts = hex_str.strip().split()
    regex = b""
    for p in parts:
        if p == "??":
            regex += b"."
        else:
            regex += bytes([int(p, 16)])
    # escapamos y luego liberamos los '.' que sí queremos como comodín
    return re.compile(re.escape(regex).replace(b"\\.", b"."), re.DOTALL)

def _hex_to_bytes(hex_str: str, target_len: int | None = None) -> bytes:
    bs = bytes(int(p, 16) for p in hex_str.strip().split() if p != "??")
    if target_len is not None:
        # ajusta si el reemplazo no tiene misma longitud
        if len(bs) < target_len:
            bs = bs.ljust(target_len, b"\x00")
        elif len(bs) > target_len:
            bs = bs[:target_len]
    return bs

def _find_all(buf: bytes, pat: str) -> List[Tuple[int,int]]:
    rx = _pattern_to_regex(pat)
    out = []
    i = 0
    while True:
        m = rx.search(buf, i)
        if not m: break
        out.append(m.span())
        i = m.start() + 1
    return out

def main():
    ap = argparse.ArgumentParser(description="Aplica reemplazos hex a un BIN (admite '??' como comodín).")
    ap.add_argument("-i","--input", required=True, help="Ruta BIN de entrada")
    ap.add_argument("-o","--output", help="Ruta BIN de salida (default: <input>.mod.bin)")
    ap.add_argument("--dry-run", action="store_true", help="Solo reporta matches, no modifica")
    ap.add_argument("--op", action="append", nargs=2, metavar=("FIND","REPLACE"),
                    help="Par find/replace en hex ej: \"12 34 ?? 78\" \"12 34 00 78\". Repite --op para varias.")
    args = ap.parse_args()

    src = Path(args.input)
    if not src.exists():
        print(f"[x] No existe: {src}", file=sys.stderr); sys.exit(1)
    data = src.read_bytes()

    if not args.op:
        print("[i] No hay --op. Ejemplo:")
        print('    --op "50 30 33 30 31" "50 30 33 30 31"  # P0301 (solo probar match)')
        sys.exit(0)

    log_lines = []
    out = bytearray(data)

    for idx, (find_hex, repl_hex) in enumerate(args.op, start=1):
        spans = _find_all(data, find_hex)
        if not spans:
            log_lines.append(f"op#{idx}: patrón no encontrado: {find_hex}")
            continue

        # aplicamos SOLO el primer match (comportamiento típico de receta)
        start, end = spans[0]
        repl = _hex_to_bytes(repl_hex, end - start)
        if not args.dry_run:
            out[start:end] = repl
        log_lines.append(f"op#{idx}: offset 0x{start:X}, len={end-start}, matches={len(spans)}")

    # escribir salida
    if args.dry_run:
        print("\n".join(log_lines))
        return

    dst = Path(args.output) if args.output else src.with_suffix(src.suffix + ".mod")
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(bytes(out))

    (dst.with_suffix(dst.suffix + ".log")).write_text("\n".join(log_lines), encoding="utf-8")
    print(f"[✓] Escrito: {dst.name}")
    print(f"[i] Log: {dst.name}.log")
    for l in log_lines: print("   ", l)

if __name__ == "__main__":
    main()
