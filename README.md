# LLM-VPN: Client-Side LLM API Gateway with Semantic Routing

An innovative network proxy that intercepts LLM API calls, classifies their semantic intent, detects PII, cryptographically signs requests, and encrypts payloads before forwarding. This implements the client-side of a novel "LLM-First VPN" architecture where network decisions are informed by semantic understanding of the request.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│ Your LLM Application (OpenAI client, Anthropic SDK, etc)     │
└────────────┬─────────────────────────────────────────────────┘
             │ HTTP Request (localhost:8080)
             ▼
┌──────────────────────────────────────────────────────────────┐
│ Stage 1: Intercept                                           │
│ • Capture request body                                       │
│ • Assign or retrieve session ID                              │
│ • Track turn index and agent depth                           │
└────────────┬─────────────────────────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────────────────────┐
│ Stage 2: Classify (Two-Tier)                                │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ Tier 1: Rule-Based (< 10ms)                              │ │
│ │ • Tool call detection                                    │ │
│ │ • System prompt detection                                │ │
│ │ • Agent delegation patterns                              │ │
│ │ • Jailbreak pattern matching                             │ │
│ │ • Streaming continuation detection                       │ │
│ └────────────┬─────────────────────────────────────────────┘ │
│              │                                               │
│    Confidence < 75%? ──→ Fall back to Tier 2               │
│              │                                               │
│              ▼                                               │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ Tier 2: Neural (TinyBERT)                                │ │
│ │ • Zero-shot classification                               │ │
│ │ • Context-aware intent detection                         │ │
│ └────────────┬─────────────────────────────────────────────┘ │
│              │                                               │
│ Parallel:    ├─→ PII Scanner (Presidio)                     │
│              │   • Names, emails, SSNs, passports           │
│              │   • Sensitivity classification               │
│              │                                               │
│              └─→ Token Estimator                             │
│                  • Heuristic: words * 1.3                   │
│                  • Accurate: tiktoken (fallback)            │
└────────────┬─────────────────────────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────────────────────┐
│ Stage 3: Envelope & Encryption                              │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ Header (Plaintext, Signed)                               │ │
│ │ • intent_class, sensitivity, token_estimate              │ │
│ │ • session_id, turn_index, agent_depth                    │ │
│ │ • routing_hint (derived from intent + sensitivity)       │ │
│ │ • integrity_hash (SHA-256 of request)                    │ │
│ │ • envelope_sig (ECDSA signature)                         │ │
│ └──────────────────────────────────────────────────────────┘ │
│                                                               │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ Payload (Encrypted)                                       │ │
│ │ • Original request body encrypted with AES-256-GCM        │ │
│ │ • IV: 96-bit random                                       │ │
│ │ • Auth tag: GCM authentication                            │ │
│ └──────────────────────────────────────────────────────────┘ │
└────────────┬─────────────────────────────────────────────────┘
             │
             ▼ X-Semantic-Envelope header (base64)
             │ X-Envelope-Session header
             │ Encrypted payload in request body
             │
┌────────────┴─────────────────────────────────────────────────┐
│ Remote LLM API (OpenAI, Anthropic, etc)                      │
└──────────────────────────────────────────────────────────────┘
```

## Intent Classes

- **tool_call**: JSON body contains `tool_calls` or `function_call` keys, or messages have a `tool` role
- **system_prompt**: Turn index is 0 or messages contain a `system` role
- **agent_delegation**: Messages contain agent keywords (subtask, delegate, on behalf of, etc.)
- **user_turn**: Standard user message with no special patterns
- **jailbreak_candidate**: Matches jailbreak signatures (ignore instructions, pretend you are, etc.)
- **streaming_continuation**: Stream flag is true and turn index > 0

## Sensitivity Levels

- **high_pii**: Contains person + location together, credit card, US SSN, passport, or medical record
- **medium_pii**: Contains email, phone, IP address, or person alone
- **low**: No PII detected

## Quick Start

### 1. Install Dependencies

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Generate Cryptographic Keys

```bash
python setup.py
```

This generates ECDSA keys (SECP256R1 curve) in the `keys/` directory:
- `keys/private.pem` — Private key for signing (DO NOT COMMIT)
- `keys/public.pem` — Public key for verification

⚠️ **WARNING**: Never commit the `keys/` directory to version control. It's in `.gitignore` by default.

### 3. Configure Environment (Optional)

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Edit `.env` to customize:
- `PROXY_PORT=8080` — Local proxy port
- `INSPECTION_API_PORT=8081` — Inspection API port
- `TOKEN_ESTIMATE_METHOD=heuristic` — Token estimation method
- `LOG_LEVEL=INFO` — Logging level

### 4. Start the Proxy

```bash
python main.py
```

This starts:
- **Local proxy** on `localhost:8080` — Intercepts LLM API calls
- **Inspection API** on `localhost:8081` — Monitor sessions and statistics

### 5. Point Your LLM Client at the Proxy

In your Python code, configure your LLM client to use the proxy:

```python
import os
os.environ['HTTP_PROXY'] = 'http://localhost:8080'
os.environ['HTTPS_PROXY'] = 'http://localhost:8080'

from openai import OpenAI
client = OpenAI()  # Will route through the proxy

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}]
)
```

### 6. Monitor with Inspection API

View active sessions and statistics:

```bash
# List all active sessions
curl http://localhost:8081/sessions

# Get details of a specific session
curl http://localhost:8081/sessions/{session-id}

# View aggregated statistics
curl http://localhost:8081/stats

# Health check
curl http://localhost:8081/health
```

Example stats response:
```json
{
  "statistics": {
    "total_requests": 42,
    "intent_distribution": {
      "user_turn": 35,
      "tool_call": 5,
      "system_prompt": 2
    },
    "sensitivity_distribution": {
      "low": 40,
      "medium_pii": 2,
      "high_pii": 0
    },
    "pii_hits": 2,
    "avg_tokens_per_request": 145.3,
    "session_stats": {
      "active_sessions": 3,
      "total_turns": 42,
      "avg_agent_depth": 1.2
    }
  }
}
```

## Envelope Schema

The `X-Semantic-Envelope` header contains a base64-encoded JSON with:

```json
{
  "intent_class": "user_turn",
  "sensitivity": "low",
  "token_estimate": 150,
  "agent_depth": 0,
  "session_id": "abc123def456",
  "turn_index": 2,
  "timestamp": 1717281957514,
  "routing_hint": "best-available",
  "integrity_hash": "sha256_hex_string",
  "envelope_sig": "ecdsa_signature_hex"
}
```

**Field Descriptions:**

| Field | Purpose |
|-------|---------|
| `intent_class` | Classification of request (tool_call, system_prompt, etc.) |
| `sensitivity` | PII sensitivity level (high_pii, medium_pii, low) |
| `token_estimate` | Approximate token count for rate limiting |
| `agent_depth` | Nesting depth for multi-turn agent interactions |
| `session_id` | Unique identifier for session (SHA256 of IP + timestamp) |
| `turn_index` | Request number within session (0-indexed) |
| `timestamp` | Unix timestamp in milliseconds |
| `routing_hint` | Gateway routing decision (domestic-only, sandbox-cluster, rate-limited, block, best-available) |
| `integrity_hash` | SHA-256 of original request for tampering detection |
| `envelope_sig` | ECDSA signature of header (excludes this field) |

### Routing Hint Rules

| Condition | Hint |
|-----------|------|
| Sensitivity = high_pii | `domestic-only` |
| Intent = tool_call | `sandbox-cluster` |
| Agent depth > 3 | `rate-limited` |
| Intent = jailbreak_candidate | `block` |
| (else) | `best-available` |

## Encryption Details

### AES-256-GCM

- **Key**: 32 bytes (256 bits) generated per session
- **IV**: 12 bytes (96 bits) random per request
- **Auth Tag**: 16 bytes (128 bits) for GCM authentication
- **Mode**: Galois/Counter Mode (authenticated encryption)

The encrypted request payload is transmitted in the request body as:

```json
{
  "encrypted_payload": "base64_ciphertext",
  "iv": "base64_iv",
  "auth_tag": "base64_auth_tag"
}
```

### ECDSA Signing

- **Curve**: SECP256R1 (P-256)
- **Hash**: SHA-256
- **Key Size**: 256 bits (32 bytes)
- **Signature**: Deterministic (RFC 6979)

The header is signed in canonical JSON form (sorted keys, no whitespace). The signature verifies that:
1. The header was created by the holder of the private key
2. The header fields have not been tampered with

## Running Tests

```bash
# Run all tests
pytest

# Run specific test suite
pytest test_classifier.py
pytest test_envelope.py
pytest test_proxy.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=. --cov-report=html
```

### Test Coverage

- **test_classifier.py**: Intent classification, PII detection, token estimation
  - Tier 1 rule detection for all 6 intent classes
  - All jailbreak patterns
  - Delegation keywords
  - Sensitivity classification for different PII types
  - Token estimation heuristics

- **test_envelope.py**: Envelope building, cryptography
  - ECDSA signing and verification
  - AES-256-GCM encryption/decryption
  - Integrity hash generation and validation
  - Envelope header serialization
  - Complete envelope building workflow

- **test_proxy.py**: Proxy behavior, session management
  - Session creation and retrieval
  - Turn index tracking
  - Session expiration and cleanup
  - Proxy endpoint detection
  - Statistics tracking

## Project Structure

```
llm-vpn/
├── main.py                     # Entry point, starts proxy and inspection API
├── setup.py                    # One-time setup: generate keys, create directories
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variables template
├── README.md                   # This file
│
├── config/
│   ├── __init__.py
│   ├── settings.py            # Configuration from .env
│   └── jailbreak_patterns.txt # Pattern library for Tier 1
│
├── classifier/  (or individual modules in root for MVP)
│   ├── intent.py              # Intent/Sensitivity enums
│   ├── rules.py               # Tier 1 rule-based classifier
│   ├── neural.py              # Tier 2 TinyBERT fallback
│   ├── pii.py                 # Presidio-based PII detection
│   └── __init__.py
│
├── envelope/  (or individual modules in root for MVP)
│   ├── schema.py              # Dataclass definitions
│   ├── crypto.py              # ECDSA, SHA-256, AES-256-GCM
│   ├── builder.py             # Envelope assembly orchestration
│   └── __init__.py
│
├── proxy/
│   ├── __init__.py
│   ├── interceptor.py         # MITMPROXY addon for interception
│   ├── session.py             # Session state and management
│   └── inspection.py          # FastAPI REST inspection API
│
├── tests/
│   ├── test_classifier.py     # Classification tests
│   ├── test_envelope.py       # Envelope and crypto tests
│   └── test_proxy.py          # Proxy and session tests
│
├── keys/                       # ⚠️ NEVER COMMIT THIS
│   ├── .gitkeep
│   ├── private.pem            # Private key (gitignored)
│   └── public.pem             # Public key
│
└── .gitignore                 # Excludes keys/ and __pycache__/
```

## Production Considerations

### Security

1. **Key Management**: Store `keys/private.pem` in a secure vault, not in source control
2. **TLS**: Proxy should run behind TLS in production (use nginx or similar)
3. **Authentication**: Add API key validation in the inspection endpoint
4. **Rate Limiting**: Implement rate limiting on the inspection API
5. **Audit Logging**: Log all intercepted requests for compliance

### Performance

1. **Tier 1 Caching**: Cache classifier results for common patterns
2. **Async Proxy**: Run proxy in async mode (migrate from mitmproxy sync)
3. **Token Estimation**: Use tiktoken for accurate counts, cache results
4. **PII Cache**: Cache Presidio analyzer instance to avoid reinitialization

### Scalability

1. **Distributed Sessions**: Use Redis for session storage across multiple proxy instances
2. **Metrics Export**: Export Prometheus metrics for monitoring
3. **Horizontal Scaling**: Deploy multiple proxy instances behind a load balancer

## Troubleshooting

### Proxy not intercepting requests

- Verify `HTTP_PROXY` and `HTTPS_PROXY` environment variables are set
- Check that the proxy is running: `curl http://localhost:8081/health`
- Verify LLM endpoint is in the `LLM_ENDPOINTS` list

### "No such file" when running setup.py

```bash
# Ensure you're in the project directory
cd llm-vpn

# Run setup
python setup.py
```

### Inspection API not responding

- Check port 8081 is not in use: `lsof -i :8081` (Unix) or `netstat -ano | findstr :8081` (Windows)
- Restart the proxy: `python main.py`

### Keys not generated

- Run `python setup.py` explicitly before starting the proxy
- Verify `keys/` directory exists and is writable

## Citation

If you use this project, please cite:

```
LLM-VPN: Client-Side Semantic Routing for LLM APIs
Author: [Your Name]
Year: 2024
```

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please:
1. Write tests for new features
2. Ensure all tests pass: `pytest`
3. Follow PEP 8 style guidelines
4. Update README for user-facing changes

---

**Last Updated**: June 2024
