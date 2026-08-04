"""Ed25519 signing and verification for immutable market packages."""

from __future__ import annotations

import zipfile
import json
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


def generate_development_key(private_path: Path, public_path: Path) -> None:
    if private_path.exists() or public_path.exists():
        raise FileExistsError("Refusing to overwrite an existing signing key")
    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.parent.mkdir(parents=True, exist_ok=True)
    private_key = Ed25519PrivateKey.generate()
    private_path.write_bytes(
        private_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    public_path.write_bytes(
        private_key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    )


def sign_market_package(package_path: Path, private_path: Path) -> None:
    private_key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("Signing key is not Ed25519")
    with zipfile.ZipFile(package_path, "a", compression=zipfile.ZIP_DEFLATED) as archive:
        manifest = archive.read("manifest.json")
        archive.writestr("signature.ed25519", private_key.sign(manifest))


def verify_market_package(package_path: Path, public_path: Path) -> bool:
    try:
        public_key = serialization.load_pem_public_key(public_path.read_bytes())
        if not isinstance(public_key, Ed25519PublicKey):
            return False
        with zipfile.ZipFile(package_path) as archive:
            names = archive.namelist()
            if names.count("signature.ed25519") != 1 or "manifest.json" not in names:
                return False
            manifest = archive.read("manifest.json")
            if json.loads(manifest).get("schema_version") != 1:
                return False
            public_key.verify(archive.read("signature.ed25519"), manifest)
        return True
    except (OSError, ValueError, InvalidSignature, KeyError, zipfile.BadZipFile):
        return False
