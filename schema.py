"""Semantic envelope schema and serialization."""

from dataclasses import dataclass, field, asdict
from typing import Optional
import json
import base64
from intent import IntentClass, SensitivityLevel


@dataclass
class SemanticEnvelopeHeader:
    """Header portion of the semantic envelope (plaintext but signed)."""
    intent_class: str  # IntentClass enum value
    sensitivity: str  # SensitivityLevel enum value
    token_estimate: int
    agent_depth: int
    session_id: str
    turn_index: int
    timestamp: int
    routing_hint: str  # derived from intent and sensitivity
    integrity_hash: str  # SHA-256 of raw prompt string
    envelope_sig: str = ""  # ECDSA signature (added during signing)
    
    def to_canonical_json(self) -> bytes:
        """Serialize to canonical JSON for signing (sig field excluded)."""
        data = asdict(self)
        data.pop("envelope_sig", None)
        return json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    
    def to_json(self) -> str:
        """Serialize to JSON including signature."""
        return json.dumps(asdict(self), separators=(",", ":"))
    
    @staticmethod
    def from_json(json_str: str) -> "SemanticEnvelopeHeader":
        """Deserialize from JSON."""
        data = json.loads(json_str)
        return SemanticEnvelopeHeader(**data)


@dataclass
class SemanticEnvelope:
    """Complete semantic envelope with encrypted payload."""
    header: SemanticEnvelopeHeader
    encrypted_payload: bytes  # AES-256-GCM encrypted original request body
    iv: bytes  # Initialization vector for AES
    auth_tag: bytes  # GCM authentication tag
    
    def header_as_base64(self) -> str:
        """Encode header as base64 for HTTP transmission."""
        header_json = self.header.to_json()
        return base64.b64encode(header_json.encode("utf-8")).decode("utf-8")
    
    def payload_as_base64(self) -> str:
        """Encode encrypted payload as base64 for HTTP transmission."""
        return base64.b64encode(self.encrypted_payload).decode("utf-8")
    
    def iv_as_base64(self) -> str:
        """Encode IV as base64."""
        return base64.b64encode(self.iv).decode("utf-8")
    
    def auth_tag_as_base64(self) -> str:
        """Encode auth tag as base64."""
        return base64.b64encode(self.auth_tag).decode("utf-8")
