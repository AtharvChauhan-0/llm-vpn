"""Envelope builder: orchestrates classification and envelope assembly."""

import json
import time
from typing import Tuple
from schema import SemanticEnvelopeHeader, SemanticEnvelope
from intent import IntentClass, SensitivityLevel
from classifier import classify_tier1, classify_tier2
from pii import classify_sensitivity, estimate_tokens
from crypto import (
    generate_sha256_hash,
    sign_header,
    encrypt_payload,
    generate_session_key,
)
import logging

logger = logging.getLogger(__name__)


def classify_request(
    body: dict,
    turn_index: int,
    agent_depth: int,
    tier2_threshold: float = 0.75,
) -> Tuple[IntentClass, float]:
    """Run two-tier classification pipeline.
    
    If Tier 1 confidence >= threshold, return Tier 1 result.
    Otherwise, run Tier 2 and return its result.
    """
    intent, confidence = classify_tier1(body, turn_index, agent_depth)
    
    logger.debug(f"Tier 1 result: {intent} (confidence: {confidence})")
    
    if confidence >= tier2_threshold:
        return intent, confidence
    
    # Tier 1 confidence too low, run Tier 2
    messages = body.get("messages", [])
    intent, confidence = classify_tier2(body, turn_index, messages)
    
    logger.info(f"Tier 2 fallback: {intent} (confidence: {confidence})")
    return intent, confidence


def derive_routing_hint(intent: IntentClass, sensitivity: SensitivityLevel) -> str:
    """Derive routing hint from intent and sensitivity.
    
    Rules:
    - If sensitivity is high_pii: "domestic-only"
    - If intent is tool_call: "sandbox-cluster"
    - If agent_depth > 3: "rate-limited" (passed separately)
    - If intent is jailbreak_candidate: "block"
    - Otherwise: "best-available"
    """
    if sensitivity == SensitivityLevel.HIGH_PII:
        return "domestic-only"
    
    if intent == IntentClass.TOOL_CALL:
        return "sandbox-cluster"
    
    if intent == IntentClass.JAILBREAK_CANDIDATE:
        return "block"
    
    return "best-available"


def build_envelope(
    original_request_body: bytes,
    session_id: str,
    turn_index: int,
    agent_depth: int,
    aes_key: bytes,
    private_key,
    tier2_threshold: float = 0.75,
    token_estimate_method: str = "heuristic",
) -> SemanticEnvelope:
    """Build complete semantic envelope from request.
    
    Args:
        original_request_body: raw request body bytes
        session_id: unique session identifier
        turn_index: turn counter in session
        agent_depth: nesting depth of agents
        aes_key: AES-256 key for payload encryption
        private_key: ECDSA private key for signing
        tier2_threshold: confidence threshold for Tier 2 fallback
        token_estimate_method: "heuristic" or "tiktoken"
    
    Returns: SemanticEnvelope with all fields populated
    """
    # Parse request body
    body_str = original_request_body.decode("utf-8")
    body = json.loads(body_str)
    
    # 1. Classify intent
    intent, confidence = classify_request(body, turn_index, agent_depth, tier2_threshold)
    
    # 2. Detect PII and sensitivity
    messages = body.get("messages", [])
    messages_text = " ".join(str(m.get("content", "")) for m in messages)
    sensitivity = classify_sensitivity(messages_text)
    
    # 3. Estimate tokens
    token_estimate = estimate_tokens(body_str, method=token_estimate_method)
    
    # 4. Generate integrity hash of raw request
    integrity_hash = generate_sha256_hash(original_request_body)
    
    # 5. Derive routing hint (noting that agent_depth > 3 check is deferred)
    routing_hint = derive_routing_hint(intent, sensitivity)
    if agent_depth > 3:
        routing_hint = "rate-limited"
    
    # 6. Create envelope header (without signature yet)
    header = SemanticEnvelopeHeader(
        intent_class=intent.value,
        sensitivity=sensitivity.value,
        token_estimate=token_estimate,
        agent_depth=agent_depth,
        session_id=session_id,
        turn_index=turn_index,
        timestamp=int(time.time() * 1000),
        routing_hint=routing_hint,
        integrity_hash=integrity_hash,
        envelope_sig="",  # Will be added after signing
    )
    
    # 7. Sign the header
    header_canonical = header.to_canonical_json()
    signature = sign_header(header_canonical, private_key)
    header.envelope_sig = signature
    
    # 8. Encrypt the payload
    ciphertext, iv, _ = encrypt_payload(original_request_body, aes_key)
    
    # The ciphertext from AESGCM includes the auth tag, so we need to extract it
    # AESGCM appends a 16-byte tag at the end
    auth_tag = ciphertext[-16:]
    encrypted_payload = ciphertext[:-16]
    
    # 9. Assemble envelope
    envelope = SemanticEnvelope(
        header=header,
        encrypted_payload=encrypted_payload,
        iv=iv,
        auth_tag=auth_tag,
    )
    
    logger.info(
        f"Envelope built: intent={intent}, sensitivity={sensitivity}, "
        f"tokens={token_estimate}, session={session_id}, turn={turn_index}"
    )
    
    return envelope
