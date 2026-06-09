"""
user_test.py — Interactive whole-system test for LLM-VPN (no networking, no model).

You type messages; each one is driven through the REAL interceptor, session
manager, and envelope builder, and the REAL inspection dashboard is queried
live. The only things faked are the mitmproxy `flow` object and the LLM server.

Run:  python user_test.py

Commands at the prompt:
    <any text>     process that message as the current user
    user <name>    switch to a different simulated user (new session)
    stats          show the live /stats dashboard
    sessions       show the live /sessions list
    help           show these commands
    quit           exit
"""

import json
import time
import base64
import threading
import urllib.request

import uvicorn

from interceptor import LLMVPNProxy
from inspection import create_inspection_app


# ── Minimal mitmproxy flow stand-in (interceptor only reads these fields) ──────
class MockHeaders(dict):
    pass


class MockRequest:
    def __init__(self, host, method, body_bytes):
        self.host = host
        self.method = method
        self._content = body_bytes
        self.headers = MockHeaders()
        self.text = None

    def get_content(self):
        return self._content


class MockClientConn:
    def __init__(self, ip):
        self.peername = (ip, 12345)


class MockFlow:
    def __init__(self, host, client_ip, message, method="POST"):
        if isinstance(message, dict):
            # Caller supplied a full request body (e.g. a tool-call shape).
            payload = message
        else:
            payload = {"model": "gpt-4",
                       "messages": [{"role": "user", "content": message}]}
        body = json.dumps(payload).encode("utf-8")
        self.request = MockRequest(host, method, body)
        self.client_conn = MockClientConn(client_ip)
        self.metadata = {}  # no timestamp => same client_ip stays one session


# Map a friendly user name -> a stable client IP (so each user keeps one session)
_USER_IPS = {}


def _ip_for(user):
    if user not in _USER_IPS:
        _USER_IPS[user] = f"10.0.0.{len(_USER_IPS) + 1}"
    return _USER_IPS[user]


# A real tool-call-shaped request body (typed text can never produce this).
TOOL_CALL_BODY = {
    "model": "gpt-4",
    "messages": [
        {"role": "user", "content": "What's the weather in Paris?"},
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": "call_1", "type": "function",
                         "function": {"name": "get_weather",
                                      "arguments": '{"city":"Paris"}'}}]},
    ],
    "tool_calls": [{"id": "call_1", "type": "function",
                    "function": {"name": "get_weather"}}],
}


def process(proxy, user, message):
    flow = MockFlow("api.openai.com", _ip_for(user), message)
    proxy.request(flow)  # the real pipeline runs here

    if "X-Semantic-Envelope" not in flow.request.headers:
        print("    --> passed through unchanged")
        return

    header = json.loads(base64.b64decode(flow.request.headers["X-Semantic-Envelope"]))
    body = json.loads(flow.request.text)
    print(f"    intent      : {header['intent_class']}")
    print(f"    sensitivity : {header['sensitivity']}")
    print(f"    routing     : {header['routing_hint']}")
    print(f"    session     : {header['session_id']}  (turn {header['turn_index']})")
    print(f"    body        : encrypted ({len(body['encrypted_payload'])} b64 chars)")


def get_json(port, path):
    return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}{path}").read())


def main():
    port = 8083
    proxy = LLMVPNProxy(
        llm_endpoints=["api.openai.com", "api.anthropic.com"],
        private_key_path="./keys/private.pem",
    )
    app = create_inspection_app(proxy)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    time.sleep(1.5)

    user = "alice"
    print("\nLLM-VPN interactive system test.")
    print(f"Inspection dashboard live at http://127.0.0.1:{port}/docs")
    print("Type a message, or a command (help, toolcall, user <name>, stats, sessions, quit).\n")

    while True:
        try:
            raw = input(f"[{user}]> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye.")
            break
        if not raw:
            continue

        low = raw.lower()
        if low in ("quit", "exit", "q"):
            print("bye.")
            break
        elif low == "help":
            print("  <text>=process | toolcall=send a tool-call request | "
                  "user <name>=switch user | stats | sessions | quit")
        elif low == "toolcall":
            print("  sending a tool-call-shaped request (not plain text)...")
            process(proxy, user, TOOL_CALL_BODY)
        elif low.startswith("user "):
            user = raw[5:].strip() or user
            print(f"  switched to user '{user}'  (session {_ip_for(user)})")
        elif low == "stats":
            print("  " + json.dumps(get_json(port, "/stats"), indent=2).replace("\n", "\n  "))
        elif low == "sessions":
            print("  " + json.dumps(get_json(port, "/sessions"), indent=2).replace("\n", "\n  "))
        else:
            process(proxy, user, raw)

    server.should_exit = True


if __name__ == "__main__":
    main()
