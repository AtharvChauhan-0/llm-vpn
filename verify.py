"""Verify all components of the LLM-VPN project are present."""

import sys
from pathlib import Path

# Expected files
REQUIRED_FILES = {
    "Core Modules": [
        "main.py",
        "setup.py",
        "intent.py",
        "crypto.py",
        "schema.py",
        "classifier.py",
        "pii.py",
        "builder.py",
        "session.py",
        "interceptor.py",
        "inspection.py",
    ],
    "Configuration": [
        "requirements.txt",
        ".env.example",
        ".gitignore",
        "config_init.py",
        "jailbreak_patterns.txt",
    ],
    "Tests": [
        "test_classifier.py",
        "test_envelope.py",
        "test_proxy.py",
    ],
    "Documentation": [
        "README.md",
        "IMPLEMENTATION.md",
        "QUICKSTART.md",
    ],
}

def verify_project():
    """Verify all required files exist."""
    print("=" * 70)
    print("LLM-VPN PROJECT VERIFICATION")
    print("=" * 70)
    
    all_good = True
    total_files = 0
    found_files = 0
    
    for category, files in REQUIRED_FILES.items():
        print(f"\n{category}:")
        for filename in files:
            path = Path(filename)
            exists = path.exists()
            status = "✓" if exists else "✗"
            total_files += 1
            if exists:
                found_files += 1
            print(f"  {status} {filename}")
            if not exists:
                all_good = False
    
    print("\n" + "=" * 70)
    print(f"RESULTS: {found_files}/{total_files} files present")
    
    if all_good:
        print("✓ PROJECT COMPLETE - All files present!")
        print("\nNext steps:")
        print("1. pip install -r requirements.txt")
        print("2. python setup.py")
        print("3. python main.py")
        print("4. pytest")
        return 0
    else:
        print("✗ PROJECT INCOMPLETE - Some files missing!")
        return 1

if __name__ == "__main__":
    sys.exit(verify_project())
