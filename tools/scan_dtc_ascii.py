# tools/scan_dtc_ascii.py
from __future__ import annotations
import sys, re
from pathlib import Path

PAT = re.compile(rb"[PBCU][0-9][0-9A-F][0-9A-F][0-9A-F]")  # P0301, U0100, etc. (hex/dec mixto)

def main():
    if len(sys.argv) < 2:
        print("Uso: python tools/scan_dtc_ascii.py archivo.bin"); return
    buf = Path(sys.argv[1]).read_bytes()
    matches = list(PAT.finditer(buf))
    if not matches:
        print("No se encontraron secuencias tipo DTC ASCII."); return

    # agrupa cercanos (< 64 bytes de distancia) como “cluster”
    clusters = []
    cur = [matches[0]]
    for m in matches[1:]:
        if m.start() - cur[-1].start() <= 64:
            cur.append(m)
        else:
            clusters.append(cur); cur = [m]
    clusters.append(cur)

    print(f"[i] Encontrados {len(matches)} DTC ascii (~ agrupados en {len(clusters)} clusters)")
    for i,group in enumerate(clusters, 1):
        start = group[0].start()
        end = group[-1].end()
        sample = b", ".join(g.group(0) for g in group[:6])
        print(f"  - Cluster #{i}: offset 0x{start:X}..0x{end:X}  (items={len(group)})  ej: {sample[:60]!r}")

if __name__ == "__main__":
    main()
