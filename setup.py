#!/usr/bin/env python3
"""Setup script to initialize directory structure and generate keys."""

import os
import sys
from pathlib import Path

# Create directory structure
dirs = [
    "config",
    "proxy",
    "classifier",
    "envelope",
    "tests",
    "keys",
]

for d in dirs:
    Path(d).mkdir(exist_ok=True)
    init_file = Path(d) / "__init__.py"
    init_file.touch()

# Generate cryptographic keys if they don't exist
keys_dir = Path("keys")
private_key_path = keys_dir / "private.pem"
public_key_path = keys_dir / "public.pem"

if not private_key_path.exists() or not public_key_path.exists():
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    
    print("Generating ECDSA keys (SECP256R1)...")
    private_key = ec.generate_private_key(ec.SECP256R1())
    
    # Save private key
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    with open(private_key_path, "wb") as f:
        f.write(private_pem)
    print(f"✓ Private key saved to {private_key_path}")
    
    # Save public key
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    with open(public_key_path, "wb") as f:
        f.write(public_pem)
    print(f"✓ Public key saved to {public_key_path}")
else:
    print("✓ Keys already exist")

print("✓ Setup complete")
