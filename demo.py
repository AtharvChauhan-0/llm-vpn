"""
demo.py — Feed a message through the LLM-VPN pipeline and see every stage.

Usage:
    python demo.py "Your message here"
    python demo.py            # then type your message when prompted
"""

import sys
import json
import base64

from builder import build_envelope
from crypto import load_private_key, generate_session_key, decrypt_payload


def show(message: str, turn_index: int = 1, agent_depth: int = 0):
    # 1. Wrap the user's message in a standard OpenAI-style request body,
    #    exactly like a real LLM client (e.g. the OpenAI SDK) would send.
    request_body = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": message}
        ],
    }
    raw_bytes = json.dumps(request_body).encode("utf-8")

    # 2. Set up a session (key + signing key). In the real proxy these are
    #    created automatically; here we make them on the spot.
    session_id = "demo-session-0001"
    aes_key = generate_session_key()
    private_key = load_private_key("./keys/private.pem")

    # 3. Run the WHOLE pipeline (classify -> detect PII -> sign -> encrypt).
    envelope = build_envelope(
        original_request_body=raw_bytes,
        session_id=session_id,
        turn_index=turn_index,
        agent_depth=agent_depth,
        aes_key=aes_key,
        private_key=private_key,
    )
    h = envelope.header

    # 4. Pretty-print what came out.
    line = "=" * 64
    print("\n" + line)
    print("  INPUT MESSAGE")
    print(line)
    print(f'  "{message}"')

    print("\n" + line)
    print("  WHAT THE SYSTEM UNDERSTOOD  (the signed header)")
    print(line)
    print(f"  Intent class    : {h.intent_class}")
    print(f"  Sensitivity     : {h.sensitivity}")
    print(f"  Token estimate  : {h.token_estimate}")
    print(f"  Routing hint    : {h.routing_hint}   <-- network decision")
    print(f"  Session ID      : {h.session_id}")
    print(f"  Turn index      : {h.turn_index}")
    print(f"  Agent depth     : {h.agent_depth}")

    print("\n" + line)
    print("  SECURITY")
    print(line)
    print(f"  Integrity hash  : {h.integrity_hash[:48]}...")
    print(f"  Signature (ECDSA): {h.envelope_sig[:48]}...")
    print(f"  Encrypted body  : {envelope.payload_as_base64()[:48]}...")
    print(f"  IV              : {envelope.iv_as_base64()}")
    print(f"  Auth tag        : {envelope.auth_tag_as_base64()}")

    # 5. Prove the encryption is reversible: decrypt it back.
    ciphertext_with_tag = envelope.encrypted_payload + envelope.auth_tag
    decrypted = decrypt_payload(ciphertext_with_tag, envelope.iv, aes_key)
    matches = decrypted == raw_bytes

    print("\n" + line)
    print("  PROOF: decrypting the locked payload returns the original")
    print(line)
    print(f"  Decrypted matches original? {matches}")
    print(f"  Decrypted content: {decrypted.decode('utf-8')}")
    print(line + "\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        msg = " ".join(sys.argv[1:])
    else:
        msg = input("Type your test message: ").strip()
    show(msg)
