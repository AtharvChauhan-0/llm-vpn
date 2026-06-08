# LLM-VPN Architecture & System Design

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Your LLM Application (OpenAI SDK, Anthropic SDK, etc.)     │
│ • Uses HTTP_PROXY environment variable                     │
│ • Sends standard LLM API requests                          │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼ HTTP Request
             │ to: api.openai.com, api.anthropic.com, etc.
             │
┌────────────┴────────────────────────────────────────────────┐
│ LOCAL PROXY (localhost:8080)                               │
│                                                             │
│ ┌──────────────────────────────────────────────────────┐  │
│ │ Stage 1: Intercept                                  │  │
│ │ • Capture HTTP request body                         │  │
│ │ • Extract JSON payload                              │  │
│ │ • Assign/retrieve session ID                        │  │
│ │ • Track turn index and agent depth                  │  │
│ └──────────────────────────────────────────────────────┘  │
│                    ↓                                       │
│ ┌──────────────────────────────────────────────────────┐  │
│ │ Stage 2: Classify (Two-Tier Pipeline)              │  │
│ │                                                      │  │
│ │ Tier 1: Rule-Based (< 10ms)                         │  │
│ │ ┌────────────────────────────────────────────────┐  │  │
│ │ │ • Tool call detection (tool_calls key)        │  │  │
│ │ │ • System prompt (turn_index=0 or system role) │  │  │
│ │ │ • Agent delegation (keywords)                 │  │  │
│ │ │ • Jailbreak patterns (15+ signatures)         │  │  │
│ │ │ • Streaming continuation (stream=true)        │  │  │
│ │ │ Returns: (intent_class, confidence)           │  │  │
│ │ └────────────────────────────────────────────────┘  │  │
│ │          ↓                                           │  │
│ │    Confidence >= 0.75? ──YES──→ Continue to Stage 3 │  │
│ │          │                                           │  │
│ │         NO                                           │  │
│ │          ↓                                           │  │
│ │ Tier 2: Neural (TinyBERT Fallback)                  │  │
│ │ ┌────────────────────────────────────────────────┐  │  │
│ │ │ • Zero-shot classification                    │  │  │
│ │ │ • Labels: tool_call, system, delegation, etc. │  │  │
│ │ │ Returns: (intent_class, confidence)           │  │  │
│ │ └────────────────────────────────────────────────┘  │  │
│ │                                                      │  │
│ │ Parallel: PII Scanner (Presidio)                    │  │
│ │ ┌────────────────────────────────────────────────┐  │  │
│ │ │ • Detect: PERSON, EMAIL, PHONE, SSN, etc.    │  │  │
│ │ │ • Classify sensitivity (HIGH/MEDIUM/LOW)      │  │  │
│ │ └────────────────────────────────────────────────┘  │  │
│ │                                                      │  │
│ │ Parallel: Token Estimator                           │  │
│ │ ┌────────────────────────────────────────────────┐  │  │
│ │ │ • Heuristic: word_count * 1.3                 │  │  │
│ │ │ • Accurate: tiktoken (fallback to heuristic)   │  │  │
│ │ └────────────────────────────────────────────────┘  │  │
│ └──────────────────────────────────────────────────────┘  │
│                    ↓                                       │
│ ┌──────────────────────────────────────────────────────┐  │
│ │ Stage 3: Build Semantic Envelope                    │  │
│ │                                                      │  │
│ │ 1. Generate Integrity Hash                          │  │
│ │    • SHA-256(original_request_body)                 │  │
│ │                                                      │  │
│ │ 2. Create Header (Plaintext)                        │  │
│ │    {                                                │  │
│ │      intent_class: "tool_call"                      │  │
│ │      sensitivity: "high_pii"                        │  │
│ │      token_estimate: 245                            │  │
│ │      session_id: "abc123def456..."                  │  │
│ │      turn_index: 2                                  │  │
│ │      agent_depth: 1                                 │  │
│ │      timestamp: 1717281957514                       │  │
│ │      routing_hint: "domestic-only"  [derived]       │  │
│ │      integrity_hash: "sha256hex..."                 │  │
│ │      envelope_sig: ""  [to be filled]               │  │
│ │    }                                                │  │
│ │                                                      │  │
│ │ 3. Sign Header                                      │  │
│ │    • Canonical JSON (sorted keys)                   │  │
│ │    • ECDSA-SHA256 signature                         │  │
│ │    • SECP256R1 private key                          │  │
│ │    • Append signature to header                     │  │
│ │                                                      │  │
│ │ 4. Encrypt Payload                                  │  │
│ │    • Original request body (bytes)                  │  │
│ │    • AES-256-GCM encryption                         │  │
│ │    • 96-bit random IV                               │  │
│ │    • 128-bit GCM auth tag                           │  │
│ │    • Session-specific key                           │  │
│ │                                                      │  │
│ │ 5. Assemble Envelope                                │  │
│ │    {                                                │  │
│ │      header: {...signed header...},                 │  │
│ │      encrypted_payload: b"...",                     │  │
│ │      iv: b"...",                                    │  │
│ │      auth_tag: b"..."                               │  │
│ │    }                                                │  │
│ └──────────────────────────────────────────────────────┘  │
│                    ↓                                       │
│ ┌──────────────────────────────────────────────────────┐  │
│ │ Modify Request                                       │  │
│ │ • Add header: X-Semantic-Envelope (base64)          │  │
│ │ • Add header: X-Envelope-Session                    │  │
│ │ • Replace body: {encrypted_payload, iv, auth_tag}  │  │
│ │ • Preserve other headers                            │  │
│ └──────────────────────────────────────────────────────┘  │
│                    ↓                                       │
│ ┌──────────────────────────────────────────────────────┐  │
│ │ Update Statistics                                    │  │
│ │ • Increment total_requests                          │  │
│ │ • Track intent_distribution                         │  │
│ │ • Track sensitivity_distribution                    │  │
│ │ • Count PII hits                                    │  │
│ │ • Sum token estimates                               │  │
│ └──────────────────────────────────────────────────────┘  │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼ Modified HTTP Request
             │ Headers: X-Semantic-Envelope, X-Envelope-Session
             │ Body: {encrypted_payload, iv, auth_tag}
             │
┌────────────┴────────────────────────────────────────────────┐
│ REMOTE LLM ENDPOINT (api.openai.com, etc.)                 │
│                                                             │
│ • Receives enriched request                               │
│ • Processes normally (gateway layer not part of MVP)      │
│ • Returns response                                         │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼ HTTP Response
             │
┌────────────┴────────────────────────────────────────────────┐
│ LOCAL PROXY (Response Handler)                             │
│ • Attach X-Envelope-Session for correlation               │
│ • Forward response to client                               │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼ HTTP Response
             │
┌────────────┴────────────────────────────────────────────────┐
│ Your LLM Application                                        │
│ • Receives response as normal                              │
└─────────────────────────────────────────────────────────────┘
```

## Component Interaction Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ main.py (Entry Point)                                      │
│ • Starts proxy on :8080                                    │
│ • Starts inspection API on :8081                           │
│ • Loads configuration from .env                            │
└──────────────────┬──────────────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
┌──────────────────┐ ┌─────────────────────────────────┐
│ interceptor.py   │ │ inspection.py (FastAPI)         │
│ (MITMPROXY)      │ │                                 │
│                  │ │ Routes:                         │
│ • request()      │ │  GET /sessions                  │
│ • response()     │ │  GET /sessions/{id}             │
│ • get_stats()    │ │  GET /stats                     │
│                  │ │  GET /health                    │
└────────┬─────────┘ └─────────────────────────────────┘
         │
         └──────────┬───────────────────────────────┐
                    │                               │
                    ▼                               ▼
            ┌──────────────────┐         ┌──────────────────────┐
            │ builder.py       │         │ session.py           │
            │                  │         │                      │
            │ • classify_req() │         │ • SessionState       │
            │ • build_envelope │         │ • SessionManager     │
            │ • derive_hint()  │         │ • get/create         │
            │                  │         │ • cleanup_expired()  │
            └────────┬─────────┘         └──────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
   ┌─────────┐ ┌──────────┐ ┌──────────┐
   │crypto.py│ │pii.py    │ │classifier│
   │         │ │          │ │.py       │
   │ • sign  │ │ • detect │ │          │
   │ • hash  │ │ • classify│ • Tier1   │
   │ • enc   │ │ • tokens │ • Tier2  │
   └─────────┘ └──────────┘ └──────────┘
        │            │            │
        └────────────┼────────────┘
                     │
                     ▼
            ┌──────────────────┐
            │ schema.py        │
            │ • SemanticEnvelope
            │ • Header         │
            └──────────────────┘
```

## Data Flow: Request Processing

```
Client Request (JSON)
    │
    ├─→ Parse JSON body
    │
    ├─→ Generate/Retrieve Session
    │   └─→ session_id = SHA256(client_ip + timestamp)
    │
    ├─→ Classify Intent (Two-Tier)
    │   ├─→ Tier 1 (Rule-Based)
    │   │   ├─→ Check tool_calls key? → TOOL_CALL
    │   │   ├─→ Check turn_index == 0? → SYSTEM_PROMPT
    │   │   ├─→ Check delegation keywords? → AGENT_DELEGATION
    │   │   ├─→ Check jailbreak patterns? → JAILBREAK_CANDIDATE
    │   │   ├─→ Check stream + turn > 0? → STREAMING_CONTINUATION
    │   │   └─→ Confidence < 0.75? → Try Tier 2
    │   │
    │   └─→ Tier 2 (Neural) [if Tier 1 < 0.75]
    │       └─→ TinyBERT zero-shot classification
    │
    ├─→ Detect PII (Parallel)
    │   ├─→ Presidio analyzer
    │   └─→ Classify: HIGH/MEDIUM/LOW
    │
    ├─→ Estimate Tokens (Parallel)
    │   ├─→ Heuristic: words * 1.3
    │   └─→ Or tiktoken if available
    │
    ├─→ Generate Integrity Hash
    │   └─→ SHA256(original_request_body)
    │
    ├─→ Derive Routing Hint
    │   ├─→ HIGH_PII? → "domestic-only"
    │   ├─→ TOOL_CALL? → "sandbox-cluster"
    │   ├─→ agent_depth > 3? → "rate-limited"
    │   ├─→ JAILBREAK? → "block"
    │   └─→ Else → "best-available"
    │
    ├─→ Create Header (JSON)
    │   ├─→ intent_class
    │   ├─→ sensitivity
    │   ├─→ token_estimate
    │   ├─→ session_id
    │   ├─→ turn_index
    │   ├─→ agent_depth
    │   ├─→ timestamp (ms)
    │   ├─→ routing_hint
    │   ├─→ integrity_hash
    │   └─→ envelope_sig (empty, to be filled)
    │
    ├─→ Sign Header
    │   ├─→ Canonical JSON (sorted)
    │   ├─→ ECDSA-SHA256(header, private_key)
    │   └─→ Add signature to header
    │
    ├─→ Encrypt Payload
    │   ├─→ Generate IV (12 bytes random)
    │   ├─→ AES-256-GCM(original_body, session_key, iv)
    │   └─→ Extract auth_tag
    │
    ├─→ Build Envelope
    │   ├─→ header (with signature)
    │   ├─→ encrypted_payload
    │   ├─→ iv
    │   └─→ auth_tag
    │
    ├─→ Update Statistics
    │   ├─→ total_requests++
    │   ├─→ intent_distribution[intent]++
    │   ├─→ sensitivity_distribution[sensitivity]++
    │   ├─→ pii_hits++ (if not LOW)
    │   └─→ total_tokens += token_estimate
    │
    └─→ Forward Modified Request
        ├─→ X-Semantic-Envelope: base64(header)
        ├─→ X-Envelope-Session: session_id
        ├─→ Body: {encrypted_payload, iv, auth_tag}
        └─→ To: remote LLM endpoint
```

## Session State Lifecycle

```
Session Creation
    │
    ├─→ session_id = SHA256(client_ip + timestamp)
    │
    ├─→ Generate session_key = 32 random bytes (AES key)
    │
    ├─→ Initialize:
    │   ├─→ turn_index = 0
    │   ├─→ agent_depth = 0
    │   ├─→ intent_history = []
    │   ├─→ created_at = now()
    │   └─→ last_active = now()
    │
    └─→ Store in SessionManager.sessions[session_id]

        ↓ Each Request in Same Session
        │
        ├─→ Retrieve session from cache
        │
        ├─→ Increment turn_index++
        │
        ├─→ Add intent to intent_history (keep last 10)
        │
        ├─→ Update last_active = now()
        │
        └─→ Process request with same session_key
        
        ↓ Every 30 Minutes (or custom timeout)
        │
        ├─→ Check: now() - last_active > TIMEOUT?
        │
        ├─→ If YES: Remove from sessions
        │
        └─→ If NO: Keep active
```

## Routing Hint Decision Tree

```
Derive Routing Hint
    │
    ├─→ sensitivity == HIGH_PII?
    │   └─→ "domestic-only"
    │
    ├─→ intent == TOOL_CALL?
    │   └─→ "sandbox-cluster"
    │
    ├─→ agent_depth > 3?
    │   └─→ "rate-limited"
    │
    ├─→ intent == JAILBREAK_CANDIDATE?
    │   └─→ "block"
    │
    └─→ Else
        └─→ "best-available"
```

## Encryption Envelope Structure

```
SemanticEnvelope
│
├─ header: SemanticEnvelopeHeader
│  │
│  ├─ intent_class: str               # "tool_call"
│  ├─ sensitivity: str                # "high_pii"
│  ├─ token_estimate: int             # 245
│  ├─ agent_depth: int                # 1
│  ├─ session_id: str                 # "abc123..."
│  ├─ turn_index: int                 # 2
│  ├─ timestamp: int                  # 1717281957514
│  ├─ routing_hint: str               # "domestic-only"
│  ├─ integrity_hash: str             # "sha256..."
│  └─ envelope_sig: str               # "ecdsa_sig_hex..."
│
├─ encrypted_payload: bytes           # AES-256 ciphertext (no tag)
│
├─ iv: bytes                          # 12-byte IV
│
└─ auth_tag: bytes                    # 16-byte GCM tag
```

## Key Generation & Storage

```
Initial Setup (python setup.py)
    │
    ├─→ Generate ECDSA key pair (SECP256R1)
    │   ├─→ private_key (32 bytes)
    │   └─→ public_key (from private_key)
    │
    ├─→ Serialize to PEM format
    │   ├─→ keys/private.pem (PKCS8, 256-bit)
    │   └─→ keys/public.pem (SubjectPublicKeyInfo)
    │
    └─→ Set permissions
        └─→ private.pem: 600 (read/write owner only)

Runtime (main.py)
    │
    ├─→ Load private_key from keys/private.pem
    │   └─→ Used for ECDSA signing
    │
    └─→ Load public_key from keys/public.pem
        └─→ Shared with gateway for verification
```

## Statistics Aggregation

```
Real-Time Statistics (GET /stats)
    │
    ├─ total_requests: int
    │  └─ Incremented per request
    │
    ├─ intent_distribution: dict
    │  ├─ "tool_call": 5
    │  ├─ "system_prompt": 2
    │  ├─ "user_turn": 35
    │  └─ ...
    │
    ├─ sensitivity_distribution: dict
    │  ├─ "low": 40
    │  ├─ "medium_pii": 2
    │  └─ "high_pii": 0
    │
    ├─ pii_hits: int
    │  └─ Count where sensitivity != "low"
    │
    ├─ avg_tokens_per_request: float
    │  └─ total_tokens / total_requests
    │
    └─ session_stats: dict
       ├─ active_sessions: int
       ├─ total_turns: int
       └─ avg_agent_depth: float
```

## Error Handling & Fallbacks

```
Classification
    │
    ├─→ Tier 1 fails? → Use Tier 1 default (USER_TURN, 0.6)
    │
    ├─→ Tier 2 fails? → Fall back to Tier 1
    │
    └─→ Both fail? → DEFAULT (USER_TURN, 0.5)

PII Detection
    │
    ├─→ Presidio fails? → Use regex fallback
    │
    └─→ Regex fails? → Assume no PII (LOW)

Token Estimation
    │
    ├─→ Tiktoken fails? → Use heuristic
    │
    └─→ Heuristic fails? → Return 1

Request Processing
    │
    ├─→ Invalid JSON? → Skip (log warning)
    │
    ├─→ Missing field? → Use default
    │
    └─→ Encryption fails? → Don't forward (log error)

Signature
    │
    └─→ Signing fails? → Abort request (security)
```

---

**Note**: This architecture is designed for the client-side proxy only. The gateway layer (receiving and processing the semantic envelope) is outside the scope of this implementation.
