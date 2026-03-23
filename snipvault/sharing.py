"""Share bundles: export/import encrypted snippet archives."""

import json
from pathlib import Path
from typing import Optional

from .crypto import encrypt_bundle, decrypt_bundle
from .vault import Vault

BUNDLE_MAGIC = b"SNIPVAULT1"  # File format identifier
BUNDLE_VERSION = 1


def export_bundle(
    vault: Vault,
    output_path: str,
    passphrase: str,
    snippet_ids: Optional[list[int]] = None,
) -> dict:
    """Export snippets as an encrypted bundle file.

    Args:
        vault: Source vault
        output_path: Path to write the .snipbundle file
        passphrase: Encryption passphrase for the bundle
        snippet_ids: Optional list of IDs to export (None = all)

    Returns:
        Dict with count and output path
    """
    if snippet_ids:
        snippets = []
        for sid in snippet_ids:
            s = vault.get(sid)
            if s:
                snippets.append(s)
    else:
        snippets = vault.export_all()

    if not snippets:
        raise ValueError("No snippets to export")

    # Strip internal fields
    export_data = {
        "version": BUNDLE_VERSION,
        "count": len(snippets),
        "snippets": [
            {
                "title": s["title"],
                "content": s["content"],
                "language": s["language"],
                "tags": s["tags"],
                "created_at": s["created_at"],
                "updated_at": s["updated_at"],
            }
            for s in snippets
        ],
    }

    encrypted = encrypt_bundle(export_data, passphrase)
    out = Path(output_path)
    with open(out, "wb") as f:
        f.write(BUNDLE_MAGIC)
        f.write(BUNDLE_VERSION.to_bytes(2, "big"))
        f.write(encrypted)

    return {"count": len(snippets), "path": str(out.resolve())}


def import_bundle(
    vault: Vault,
    bundle_path: str,
    passphrase: str,
) -> dict:
    """Import snippets from an encrypted bundle file.

    Args:
        vault: Target vault
        bundle_path: Path to the .snipbundle file
        passphrase: Decryption passphrase

    Returns:
        Dict with count of imported snippets
    """
    path = Path(bundle_path)
    if not path.exists():
        raise FileNotFoundError(f"Bundle not found: {bundle_path}")

    with open(path, "rb") as f:
        magic = f.read(len(BUNDLE_MAGIC))
        if magic != BUNDLE_MAGIC:
            raise ValueError("Invalid bundle file (bad magic bytes)")

        version_bytes = f.read(2)
        version = int.from_bytes(version_bytes, "big")
        if version > BUNDLE_VERSION:
            raise ValueError(
                f"Bundle version {version} not supported (max: {BUNDLE_VERSION})"
            )

        encrypted = f.read()

    data = decrypt_bundle(encrypted, passphrase)
    snippets = data.get("snippets", [])
    count = vault.import_snippets(snippets)

    return {"count": count, "total_in_bundle": data.get("count", len(snippets))}


def list_bundle_info(bundle_path: str, passphrase: str) -> dict:
    """Peek at bundle metadata without importing.

    Returns:
        Dict with version, count, and snippet titles/languages.
    """
    path = Path(bundle_path)
    if not path.exists():
        raise FileNotFoundError(f"Bundle not found: {bundle_path}")

    with open(path, "rb") as f:
        magic = f.read(len(BUNDLE_MAGIC))
        if magic != BUNDLE_MAGIC:
            raise ValueError("Invalid bundle file")
        version_bytes = f.read(2)
        version = int.from_bytes(version_bytes, "big")
        encrypted = f.read()

    data = decrypt_bundle(encrypted, passphrase)
    snippets = data.get("snippets", [])

    return {
        "version": version,
        "count": len(snippets),
        "snippets": [
            {
                "title": s["title"],
                "language": s.get("language", ""),
                "tags": s.get("tags", []),
            }
            for s in snippets
        ],
    }
