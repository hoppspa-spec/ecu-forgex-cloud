#!/usr/bin/env python3
"""
patcher_cli.py
Plantilla segura para un "binary patcher" que genera Bin.MOD.zip

Uso (ejemplo):
python patcher_cli.py --bin original.bin --descriptor descriptor.json --out ./out

Lo que hace:
- valida hash si viene en descriptor
- ejecuta apply_patch_logic(...) -> debe devolver path a modified.bin
- genera metadata.json (bin_hash_before/after, engine_id...)
- firma metadata.json con clave RSA local (demo)
- empaqueta Bin.MOD.zip con modified.bin, metadata.json, signature.sig y revert_package.zip
"""

import argparse
import json
import hashlib
from pathlib import Path
import shutil
import zipfile
import datetime
import sys

# cryptography for demo signature (use KMS/HSM en prod)
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

APP_DIR = Path("motor_storage")
APP_DIR.mkdir(exist_ok=True)

KEY_PRIV = APP_DIR / "private_key.pem"
KEY_PUB = APP_DIR / "public_key.pem"

def ensure_keys():
    if not KEY_PRIV.exists():
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        priv = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        )
        pub = key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        KEY_PRIV.write_bytes(priv)
        KEY_PUB.write_bytes(pub)

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()

# -------------------------------
# PUNTO DE EXTENSIÓN (TU LÓGICA PRIVADA)
# -------------------------------
def apply_patch_logic(original_bin_path: Path, descriptor: dict, work_dir: Path) -> Path:
    """
    Implementá TU lógica privada aquí.
    - original_bin_path: Path al BIN original
    - descriptor: dict con lo solicitado por el usuario
    - work_dir: carpeta temporal donde escribir modified.bin

    Debe devolver Path al archivo modified.bin dentro work_dir.

    EJEMPLO SEGURO POR DEFECTO: copia el original -> modified.bin (placeholder).
    Reemplazá esto con tu implementación local.
    """
    modified = work_dir / "modified.bin"
    shutil.copyfile(original_bin_path, modified)
    return modified

# -------------------------------
# Firma y empaquetado
# -------------------------------
def sign_bytes(data: bytes) -> bytes:
    priv = serialization.load_pem_private_key(KEY_PRIV.read_bytes(), password=None)
    sig = priv.sign(
        data,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    return sig

def create_revert_package(original_bin: Path, work_dir: Path, patch_id: str) -> Path:
    rp = work_dir / f"{patch_id}_revert.zip"
    with zipfile.ZipFile(rp, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.write(original_bin, arcname="original.bin")
        # optional: include minimal revert metadata
        revert_meta = {"patch_id": patch_id, "created_at": datetime.datetime.utcnow().isoformat() + "Z"}
        z.writestr("revert_metadata.json", json.dumps(revert_meta, indent=2, ensure_ascii=False))
    return rp

def create_binmod_zip(modified_bin: Path, metadata: dict, signature: bytes, revert_package: Path, zip_out: Path):
    # write metadata to temporary location
    tmpdir = modified_bin.parent
    meta_path = tmpdir / "metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
    sig_path = tmpdir / "signature.sig"
    sig_path.write_bytes(signature)
    # create zip
    with zipfile.ZipFile(zip_out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.write(modified_bin, arcname="modified.bin")
        z.write(meta_path, arcname="metadata.json")
        z.write(sig_path, arcname="signature.sig")
        z.write(revert_package, arcname=revert_package.name)
    return zip_out

# -------------------------------
# CLI principal
# -------------------------------
def main():
    parser = argparse.ArgumentParser(description="Patcher CLI (skeleton).")
    parser.add_argument("--bin", required=True, help="Path to original.bin")
    parser.add_argument("--descriptor", required=True, help="Patch descriptor JSON (PatchDescriptor)")
    parser.add_argument("--out", default="./out", help="Output directory")
    parser.add_argument("--engine-id", default="motor_plugin_local_v1", help="Engine identifier")
    args = parser.parse_args()

    original_bin = Path(args.bin).resolve()
    descriptor_path = Path(args.descriptor).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    ensure_keys()

    if not original_bin.exists():
        print("ERROR: original bin not found:", original_bin, file=sys.stderr); sys.exit(2)
    if not descriptor_path.exists():
        print("ERROR: descriptor not found:", descriptor_path, file=sys.stderr); sys.exit(2)

    descriptor = json.loads(descriptor_path.read_text())

    patch_id = descriptor.get("patch_id") or ("patch-" + datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S"))
    work_dir = out_dir / patch_id
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    # basic audit
    audit_lines = [f"{datetime.datetime.utcnow().isoformat()}Z - received patch {patch_id}"]
    (work_dir / "audit_trail.log").write_text("\n".join(audit_lines))

    # optional: validate hash if provided
    provided_hash = descriptor.get("bin_hash")
    actual_hash = sha256_file(original_bin)
    if provided_hash:
        if provided_hash != actual_hash:
            print("ERROR: bin_hash mismatch. provided:", provided_hash, "actual:", actual_hash, file=sys.stderr)
            sys.exit(3)

    # CALL YOUR PRIVATE LOGIC HERE
    modified_bin = apply_patch_logic(original_bin, descriptor, work_dir)
    if not modified_bin.exists():
        print("ERROR: modified.bin not generated by apply_patch_logic", file=sys.stderr); sys.exit(4)

    # build metadata
    metadata = {
        "patch_id": patch_id,
        "bin_hash_before": actual_hash,
        "bin_hash_after": sha256_file(modified_bin),
        "engine_id": args.engine_id,
        "engine_version": "0.1.0",
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "descriptor_summary": {
            "objectives_count": len(descriptor.get("objectives", [])) if isinstance(descriptor.get("objectives", []), list) else 0
        }
    }

    # sign metadata
    signature = sign_bytes(json.dumps(metadata, indent=2, ensure_ascii=False).encode("utf-8"))

    # create revert package
    revert_pkg = create_revert_package(original_bin, work_dir, patch_id)

    # create Bin.MOD.zip
    zip_out = out_dir / f"{patch_id}_Bin.MOD.zip"
    create_binmod_zip(modified_bin, metadata, signature, revert_pkg, zip_out)

    print("Bin.MOD generated:", zip_out.resolve())
    print("metadata:", json.dumps(metadata, indent=2, ensure_ascii=False))
    print("public key:", KEY_PUB.resolve())

if __name__ == "__main__":
    main()