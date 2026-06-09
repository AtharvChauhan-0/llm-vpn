"""
inspect_packet.py — Type your own message, see the actual packet LLM-VPN builds.

This drives the REAL interceptor, so what you see is the genuine outgoing
HTTP request (headers + encrypted body) that would be sent over the wire.

Run:  python inspect_packet.py
Then type messages. Type 'quit' (or Ctrl+C) to exit.
"""

import json
import base64

from interceptor import LLMVPNProxy


# ── Minimal mitmproxy flow stand-in (interceptor only reads these fields) ──────
class MockHeaders(dict):
    pass


class MockRequest:
    def __init__(self, host, path, method, body_bytes):
        self.host = host
        self.path = path
        self.method = method
        self._content = body_bytes
        self.headers = MockHeaders({
            "Host": host,
            "Content-Type": "application/json",
            "Authorization": "Bearer sk-REDACTED",
        })
        self.text = None

    def get_content(self):
        return self._content


class MockClientConn:
    def __init__(self, ip):
        self.peername = (ip, 12345)


class MockFlow:
    def __init__(self, host, path, message):
        body = json.dumps({
            "model": "gpt-4",
            "messages": [{"role": "user", "content": message}],
        }).encode("utf-8")
        self.request = MockRequest(host, path, "POST", body)
        self.client_conn = MockClientConn("10.0.0.1")
        self.metadata = {}


def inspect(proxy, message):
    host = "api.openai.com"
    path = "/v1/chat/completions"
    flow = MockFlow(host, path, message)

    # Run the REAL pipeline — this is what builds the packet.
    proxy.request(flow)

    line = "-" * 70
    print("\n" + "=" * 70)
    print("  THE PACKET THAT WOULD GO ON THE WIRE")
    print("=" * 70)

    # 1. Request line + headers (the raw outgoing HTTP request).
    print(f"\n  POST https://{host}{path} HTTP/1.1")
    for k, v in flow.request.headers.items():
        shown = v if len(str(v)) <= 60 else str(v)[:57] + "..."
        print(f"  {k}: {shown}")

    # 2. The encrypted body.
    print("\n  --- Body (encrypted) ---")
    body = json.loads(flow.request.text)
    for k, v in body.items():
        shown = v if len(v) <= 60 else v[:57] + "..."
        print(f"    {k}: {shown}")

    # 3. Decode the X-Semantic-Envelope header so you can read what the
    #    network would see in plaintext (the signed metadata).
    print("\n" + line)
    print("  DECODED X-Semantic-Envelope  (the readable, signed metadata)")
    print(line)
    env_b64 = flow.request.headers["X-Semantic-Envelope"]
    header = json.loads(base64.b64decode(env_b64))
    for k, v in header.items():
        shown = v if not isinstance(v, str) or len(v) <= 60 else v[:57] + "..."
        print(f"    {k:16}: {shown}")
    print("=" * 70)


def main():
    proxy = LLMVPNProxy(
        llm_endpoints=["api.openai.com", "api.anthropic.com"],
        private_key_path="./keys/private.pem",
    )
    print("\nLLM-VPN packet inspector. Type a message and press Enter.")
    print("Type 'quit' to exit.\n")
    while True:
        try:
            msg = input("message> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye.")
            break
        if not msg:
            continue
        if msg.lower() in ("quit", "exit", "q"):
            print("bye.")
            break
        inspect(proxy, msg)


if __name__ == "__main__":
    main()
