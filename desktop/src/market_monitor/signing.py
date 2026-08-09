"""Ed25519 + ECDSA P-256 signing and verification for immutable market packages.

Android 13 devices from some OEMs do not expose ``Signature "Ed25519"``, which
made imports fail with ``NoSuchAlgorithmException`` that the verifier mapped to
``STRUCTURE``.  New packages therefore carry both an Ed25519 signature and an
ECDSA P-256 signature; Android verifies either one and falls back if Ed25519 is
unavailable.  Existing Ed25519-only packages remain verifiable.
"""

from __future__ import annotations

import zipfile
import json
import hashlib
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
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


def generate_ecdsa_key(private_path: Path, public_path: Path) -> None:
    """Generate a P-256 (prime256v1) key pair used by Android fallback verification."""

    if private_path.exists() or public_path.exists():
        raise FileExistsError("Refusing to overwrite an existing ECDSA signing key")
    private_path.parent.mkdir(parents=True, exist_ok=True)
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )


def sign_market_package(
    package_path: Path,
    private_path: Path,
    ecdsa_private_path: Path | None = None,
) -> None:
    """Sign ``manifest.json`` with Ed25519 and, when the key exists, ECDSA P-256."""

    private_key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("Signing key is not Ed25519")
    with zipfile.ZipFile(package_path, "a", compression=zipfile.ZIP_DEFLATED) as archive:
        manifest = archive.read("manifest.json")
        archive.writestr("signature.ed25519", private_key.sign(manifest))
        if ecdsa_private_path is not None and ecdsa_private_path.is_file():
            ecdsa_key = serialization.load_pem_private_key(ecdsa_private_path.read_bytes(), password=None)
            if not isinstance(ecdsa_key, ec.EllipticCurvePrivateKey):
                raise ValueError("ECDSA signing key is not an elliptic-curve private key")
            archive.writestr(
                "signature.ecdsa",
                ecdsa_key.sign(manifest, ec.ECDSA(hashes.SHA256())),
            )


def verify_market_package(
    package_path: Path,
    public_path: Path,
    ecdsa_public_path: Path | None = None,
) -> bool:
    """Verify a package with either signature present (Ed25519 preferred)."""

    try:
        public_key = serialization.load_pem_public_key(public_path.read_bytes())
        if not isinstance(public_key, Ed25519PublicKey):
            return False
        ecdsa_public_key = None
        if ecdsa_public_path is not None and ecdsa_public_path.is_file():
            loaded = serialization.load_pem_public_key(ecdsa_public_path.read_bytes())
            if isinstance(loaded, ec.EllipticCurvePublicKey):
                ecdsa_public_key = loaded
        with zipfile.ZipFile(package_path) as archive:
            names = archive.namelist()
            if names.count("signature.ed25519") != 1 or "manifest.json" not in names:
                return False
            manifest = archive.read("manifest.json")
            manifest_document = json.loads(manifest)
            if manifest_document.get("schema_version") != 1:
                return False
            for partition in manifest_document.get("partitions", []):
                for file_metadata in partition.get("files", []):
                    name = file_metadata["name"]
                    expected = file_metadata["sha256"]
                    if names.count(name) != 1:
                        return False
                    if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                        return False
            ed25519_ok = True
            try:
                public_key.verify(archive.read("signature.ed25519"), manifest)
            except InvalidSignature:
                ed25519_ok = False
            ecdsa_ok = False
            if "signature.ecdsa" in names and ecdsa_public_key is not None:
                try:
                    ecdsa_public_key.verify(
                        archive.read("signature.ecdsa"),
                        manifest,
                        ec.ECDSA(hashes.SHA256()),
                    )
                    ecdsa_ok = True
                except InvalidSignature:
                    ecdsa_ok = False
            if not (ed25519_ok or ecdsa_ok):
                return False
        return True
    except (OSError, ValueError, InvalidSignature, KeyError, zipfile.BadZipFile):
        return False
