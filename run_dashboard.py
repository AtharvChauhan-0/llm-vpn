"""
run_dashboard.py — Live LLM-VPN inspection dashboard + interactive traffic input.

The inspection API runs in the background (open it in your browser) while you
type messages in this terminal. Every message you send updates the stats and
sessions that the browser shows — refresh the browser to watch them change.

Run:  python run_dashboard.py
Open: http://127.0.0.1:8081/docs      (interactive Swagger UI)
      http://127.0.0.1:8081/stats     (raw JSON, refresh to update)
      http://127.0.0.1:8081/sessions

At the terminal prompt:
    <any text>     send that message as the current user (updates dashboard)
    user <name>    switch to a different user (new session)
    stats          print the live stats here in the terminal
    quit           stop the server and exit
"""

import json
import time
import base64
import threading
import urllib.request

import uvicorn

from interceptor import LLMVPNProxy
from inspection import create_inspection_app


# ── Minimal mitmproxy flow stand-in ───────────────────────────────────────────
class MockHeaders(dict):
    pass


class MockRequest:
    def __init__(self, host, method, body):
        self.host = host
        self.method = method
        self._content = body
        self.headers = MockHeaders()
        self.text = None

    def get_content(self):
        return self._content


class MockClientConn:
    def __init__(self, ip):
        self.peername = (ip, 12345)


class MockFlow:
    def __init__(self, client_ip, message):
        body = json.dumps({
            "model": "gpt-4",
            "messages": [{"role": "user", "content": message}],
        }).encode("utf-8")
        self.request = MockRequest("api.openai.com", "POST", body)
        self.client_conn = MockClientConn(client_ip)
        self.metadata = {}


_USER_IPS = {}


def _ip_for(user):
    if user not in _USER_IPS:
        _USER_IPS[user] = f"10.0.0.{len(_USER_IPS) + 1}"
    return _USER_IPS[user]


def process(proxy, user, message):
    flow = MockFlow(_ip_for(user), message)
    proxy.request(flow)
    if "X-Semantic-Envelope" not in flow.request.headers:
        print("    --> passed through unchanged")
        return
    h = json.loads(base64.b64decode(flow.request.headers["X-Semantic-Envelope"]))
    print(f"    intent={h['intent_class']}  sensitivity={h['sensitivity']}  "
          f"routing={h['routing_hint']}  (session {h['session_id'][:8]} turn {h['turn_index']})")
    print("    --> dashboard updated. Refresh your browser to see it.")


def get_stats(port):
    return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/stats").read())


def main():
    port = 8081
    proxy = LLMVPNProxy(
        llm_endpoints=["api.openai.com", "api.anthropic.com"],
        private_key_path="./keys/private.pem",
    )
    app = create_inspection_app(proxy)

    # Server in the background so the terminal stays interactive.
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    time.sleep(1.5)

    print("\n" + "=" * 62)
    print("  LLM-VPN Inspection Dashboard is LIVE")
    print("=" * 62)
    print(f"  Open in your browser (keep it open, refresh to update):")
    print(f"    http://127.0.0.1:{port}/docs      <- interactive UI")
    print(f"    http://127.0.0.1:{port}/stats     <- raw stats JSON")
    print(f"    http://127.0.0.1:{port}/sessions  <- active sessions")
    print()
    print("  Type messages below; each one updates the dashboard.")
    print("  Commands: user <name> | stats | quit")
    print("=" * 62 + "\n")

    user = "alice"
    while True:
        try:
            raw = input(f"[{user}]> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nstopping server. bye.")
            break
        if not raw:
            continue
        low = raw.lower()
        if low in ("quit", "exit", "q"):
            print("stopping server. bye.")
            break
        elif low.startswith("user "):
            user = raw[5:].strip() or user
            print(f"  switched to user '{user}'")
        elif low == "stats":
            print("  " + json.dumps(get_stats(port), indent=2).replace("\n", "\n  "))
        else:
            process(proxy, user, raw)

    server.should_exit = True


if __name__ == "__main__":
    main()
