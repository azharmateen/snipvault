"""AES-256-GCM encryption with PBKDF2 key derivation."""

import os
import json
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32  # 256 bits
ITERATIONS = 480_000


def derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from passphrase using PBKDF2-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=ITERATIONS,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt(plaintext: str, passphrase: str) -> str:
    """Encrypt plaintext with AES-256-GCM. Returns base64-encoded blob.

    Format: base64(salt || nonce || ciphertext+tag)
    """
    salt = os.urandom(SALT_SIZE)
    key = derive_key(passphrase, salt)
    nonce = os.urandom(NONCE_SIZE)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    blob = salt + nonce + ciphertext
    return base64.b64encode(blob).decode("ascii")


def decrypt(encoded: str, passphrase: str) -> str:
    """Decrypt a base64-encoded AES-256-GCM blob."""
    blob = base64.b64decode(encoded)
    salt = blob[:SALT_SIZE]
    nonce = blob[SALT_SIZE : SALT_SIZE + NONCE_SIZE]
    ciphertext = blob[SALT_SIZE + NONCE_SIZE :]
    key = derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


def encrypt_bundle(data: dict, passphrase: str) -> bytes:
    """Encrypt a dict as JSON -> AES-256-GCM -> raw bytes for file storage."""
    plaintext = json.dumps(data, ensure_ascii=False)
    salt = os.urandom(SALT_SIZE)
    key = derive_key(passphrase, salt)
    nonce = os.urandom(NONCE_SIZE)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return salt + nonce + ciphertext


def decrypt_bundle(raw: bytes, passphrase: str) -> dict:
    """Decrypt raw bytes -> JSON dict."""
    salt = raw[:SALT_SIZE]
    nonce = raw[SALT_SIZE : SALT_SIZE + NONCE_SIZE]
    ciphertext = raw[SALT_SIZE + NONCE_SIZE :]
    key = derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(plaintext.decode("utf-8"))
