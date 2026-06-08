"""Cryptographic primitives: signing, hashing, and encryption."""

import hashlib
import os
from typing import Tuple
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def load_private_key(path: str):
    """Load ECDSA private key from PEM file."""
    with open(path, "rb") as f:
        key_data = f.read()
    return serialization.load_pem_private_key(key_data, password=None)


def load_public_key(path: str):
    """Load ECDSA public key from PEM file."""
    with open(path, "rb") as f:
        key_data = f.read()
    return serialization.load_pem_public_key(key_data)


def generate_sha256_hash(data: bytes) -> str:
    """Generate SHA-256 hash of data."""
    return hashlib.sha256(data).hexdigest()


def sign_header(header_canonical: bytes, private_key) -> str:
    """Sign header with ECDSA private key and return hex signature."""
    signature = private_key.sign(header_canonical, ec.ECDSA(hashes.SHA256()))
    return signature.hex()


def verify_signature(header_canonical: bytes, signature_hex: str, public_key) -> bool:
    """Verify ECDSA signature against public key."""
    try:
        signature_bytes = bytes.fromhex(signature_hex)
        public_key.verify(signature_bytes, header_canonical, ec.ECDSA(hashes.SHA256()))
        return True
    except Exception:
        return False


def encrypt_payload(payload: bytes, key: bytes) -> Tuple[bytes, bytes, bytes]:
    """Encrypt payload with AES-256-GCM.
    
    Returns: (ciphertext_with_tag, iv, key)
    The ciphertext includes the GCM authentication tag appended.
    """
    iv = os.urandom(12)  # 96-bit IV for GCM
    aesgcm = AESGCM(key)
    # encrypt() returns ciphertext with auth tag appended
    ciphertext = aesgcm.encrypt(iv, payload, None)
    return ciphertext, iv, key


def decrypt_payload(ciphertext: bytes, iv: bytes, key: bytes) -> bytes:
    """Decrypt AES-256-GCM encrypted payload.
    
    Args:
        ciphertext: encrypted data with auth tag appended
        iv: initialization vector
        key: 32-byte AES key
    
    Returns: decrypted plaintext
    
    Raises: InvalidTag if authentication fails
    """
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(iv, ciphertext, None)


def generate_session_key() -> bytes:
    """Generate a 32-byte AES-256 key."""
    return os.urandom(32)
