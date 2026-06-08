"""Initialize and run LLM-VPN project setup and tests."""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Create directory structure
print("Creating directory structure...")
dirs = ["config", "proxy", "classifier", "envelope", "tests", "keys"]
for d in dirs:
    Path(d).mkdir(exist_ok=True)

# Create __init__.py files
print("Creating __init__.py files...")
for d in ["config", "proxy", "classifier", "envelope", "tests"]:
    init_file = Path(d) / "__init__.py"
    if not init_file.exists():
        init_file.write_text(f"# {d} package\n")

# Generate keys
print("\nGenerating cryptographic keys...")
from crypto import load_private_key
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

keys_dir = Path("keys")
keys_dir.mkdir(exist_ok=True)

private_key_path = keys_dir / "private.pem"
public_key_path = keys_dir / "public.pem"

if not private_key_path.exists() or not public_key_path.exists():
    print("  Generating ECDSA keys (SECP256R1)...")
    private_key = ec.generate_private_key(ec.SECP256R1())
    
    # Save private key
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    with open(private_key_path, "wb") as f:
        f.write(private_pem)
    print(f"  ✓ Private key saved to {private_key_path}")
    
    # Save public key
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    with open(public_key_path, "wb") as f:
        f.write(public_pem)
    print(f"  ✓ Public key saved to {public_key_path}")
else:
    print("  ✓ Keys already exist")

# Setup config directory
print("\nSetting up configuration...")
config_dir = Path("config")
config_dir.mkdir(exist_ok=True)

# Copy jailbreak patterns
patterns_file = config_dir / "jailbreak_patterns.txt"
if not patterns_file.exists():
    print("  Creating jailbreak patterns...")
    patterns_file.write_text(
        "ignore previous instructions\n"
        "ignore all instructions\n"
        "pretend you are\n"
        "your true self\n"
        "dan mode\n"
        "jailbreak\n"
        "do anything now\n"
        "no restrictions\n"
        "bypass your\n"
        "forget you are an ai\n"
        "disregard all previous\n"
        "new instructions\n"
        "system override\n"
        "admin mode\n"
        "developer mode\n"
        "unrestricted mode\n"
    )
    print(f"  ✓ Jailbreak patterns created at {patterns_file}")

# Copy settings file
settings_file = config_dir / "settings.py"
if not settings_file.exists():
    print("  Creating settings file...")
    # Import and copy the settings from root
    settings_content = Path("config_init.py").read_text()
    # We'll just reference the root settings.py instead
    settings_file.write_text(
        """import os
from dotenv import load_dotenv

load_dotenv()

# Proxy configuration
PROXY_PORT = int(os.getenv("PROXY_PORT", 8080))
INSPECTION_API_PORT = int(os.getenv("INSPECTION_API_PORT", 8081))

# Key paths
KEY_DIR = os.getenv("KEY_DIR", "./keys")
PRIVATE_KEY_PATH = os.path.join(KEY_DIR, "private.pem")
PUBLIC_KEY_PATH = os.path.join(KEY_DIR, "public.pem")

# LLM endpoints to intercept
LLM_ENDPOINTS = [
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "localhost",
    "127.0.0.1",
]

# Classification thresholds
TIER2_CONFIDENCE_THRESHOLD = float(os.getenv("TIER2_CONFIDENCE_THRESHOLD", 0.75))
SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", 30))

# PII detection
PII_SCORE_THRESHOLD = float(os.getenv("PII_SCORE_THRESHOLD", 0.6))

# Token estimation
TOKEN_ESTIMATE_METHOD = os.getenv("TOKEN_ESTIMATE_METHOD", "heuristic")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Jailbreak patterns
JAILBREAK_PATTERNS_PATH = os.getenv(
    "JAILBREAK_PATTERNS_PATH", "./config/jailbreak_patterns.txt"
)
""")
    print(f"  ✓ Settings file created at {settings_file}")

print("\n✓ Setup complete!")
print("\nNext steps:")
print("1. pip install -r requirements.txt")
print("2. python main.py")
print("3. In another terminal: pytest")
print("\nTo use the proxy:")
print("  export HTTP_PROXY=http://localhost:8080")
print("  export HTTPS_PROXY=http://localhost:8080")
