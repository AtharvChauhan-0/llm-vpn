"""Main entry point for LLM-VPN proxy."""

import os
import sys
import logging
from pathlib import Path
import asyncio
import threading
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Ensure we can import from root directory
sys.path.insert(0, str(Path(__file__).parent))

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
import uvicorn
from inspection import create_inspection_app
from interceptor import LLMVPNProxy


def setup_keys(key_dir: str = "./keys"):
    """Generate cryptographic keys if they don't exist."""
    key_dir = Path(key_dir)
    key_dir.mkdir(exist_ok=True)
    
    private_key_path = key_dir / "private.pem"
    public_key_path = key_dir / "public.pem"
    
    if private_key_path.exists() and public_key_path.exists():
        logger.info("✓ Keys already exist")
        return
    
    logger.info("Generating ECDSA keys (SECP256R1)...")
    private_key = ec.generate_private_key(ec.SECP256R1())
    
    # Save private key
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    with open(private_key_path, "wb") as f:
        f.write(private_pem)
    logger.info(f"✓ Private key saved to {private_key_path}")
    
    # Save public key
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    with open(public_key_path, "wb") as f:
        f.write(public_pem)
    logger.info(f"✓ Public key saved to {public_key_path}")


def setup_jailbreak_patterns(patterns_path: str = "./config/jailbreak_patterns.txt"):
    """Create default jailbreak patterns file if it doesn't exist."""
    patterns_path = Path(patterns_path)
    patterns_path.parent.mkdir(parents=True, exist_ok=True)
    
    if patterns_path.exists():
        logger.info("✓ Jailbreak patterns file already exists")
        return
    
    default_patterns = [
        "ignore previous instructions",
        "ignore all instructions",
        "pretend you are",
        "your true self",
        "dan mode",
        "jailbreak",
        "do anything now",
        "no restrictions",
        "bypass your",
        "forget you are an ai",
        "disregard all previous",
        "new instructions",
        "system override",
        "admin mode",
    ]
    
    with open(patterns_path, "w") as f:
        for pattern in default_patterns:
            f.write(pattern + "\n")
    
    logger.info(f"✓ Created default jailbreak patterns at {patterns_path}")


def run_inspection_api(port: int = 8081):
    """Run the inspection API in a separate thread."""
    # Defer import to avoid circular dependency issues
    proxy = LLMVPNProxy(
        llm_endpoints=[
            "api.openai.com",
            "api.anthropic.com",
            "generativelanguage.googleapis.com",
            "localhost",
            "127.0.0.1",
        ],
        private_key_path="./keys/private.pem",
    )
    
    app = create_inspection_app(proxy)
    
    logger.info(f"Starting inspection API on port {port}...")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


def main():
    """Main entry point."""
    logger.info("LLM-VPN Proxy Starting")
    
    # Setup
    setup_keys(key_dir="./keys")
    setup_jailbreak_patterns(patterns_path="./config/jailbreak_patterns.txt")
    
    # Start inspection API in background
    api_thread = threading.Thread(
        target=run_inspection_api,
        args=(8081,),
        daemon=True,
    )
    api_thread.start()
    
    logger.info("Inspection API thread started")
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    main()
