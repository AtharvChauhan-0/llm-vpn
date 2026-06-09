"""
test_tool_call.py — Test the tool_call intent through the full pipeline.

tool_call is detected from the request STRUCTURE (the presence of tool_calls /
function_call keys, or a tools array with a tool-role message), NOT from the
message text. This script feeds real tool-call-shaped request bodies through
the whole envelope pipeline so you can see them classified as tool_call and
routed to the 'sandbox-cluster'.

Run:  python test_tool_call.py
"""

import json

from builder import build_envelope
from crypto import load_private_key, generate_session_key


# Realistic tool-call request bodies, as the OpenAI / Anthropic SDKs send them.
EXAMPLES = {
    "assistant emits a tool_calls array (OpenAI style)": {
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
    },
    "legacy function_call key": {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "weather please"}],
        "function_call": {"name": "get_weather", "arguments": '{"city":"Paris"}'},
    },
    "tool result being sent back (tools + role=tool)": {
        "model": "gpt-4",
        "tools": [{"type": "function", "function": {"name": "get_weather"}}],
        "messages": [
            {"role": "user", "content": "weather in Paris?"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]},
            {"role": "tool", "tool_call_id": "c1", "content": "72F, sunny"},
        ],
    },
}


def main():
    private_key = load_private_key("./keys/private.pem")

    print("=" * 66)
    print("  Testing tool_call detection through the full pipeline")
    print("=" * 66)

    for label, body in EXAMPLES.items():
        raw = json.dumps(body).encode("utf-8")
        envelope = build_envelope(
            original_request_body=raw,
            session_id="tooltest",
            turn_index=2,            # turn>0 so it isn't caught as a system prompt
            agent_depth=0,
            aes_key=generate_session_key(),
            private_key=private_key,
        )
        h = envelope.header
        ok = "OK " if h.intent_class == "tool_call" else "XX "
        print(f"\n  {ok}{label}")
        print(f"      intent_class : {h.intent_class}")
        print(f"      routing_hint : {h.routing_hint}")

    print("\n" + "=" * 66)
    print("  Expected: every case -> intent_class=tool_call, routing=sandbox-cluster")
    print("=" * 66)


if __name__ == "__main__":
    main()
