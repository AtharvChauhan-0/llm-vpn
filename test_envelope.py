"""Tests for envelope building and cryptography."""

import pytest
import json
import hashlib
from schema import SemanticEnvelopeHeader, SemanticEnvelope
from intent import IntentClass, SensitivityLevel
from builder import build_envelope, derive_routing_hint
from crypto import (
    generate_sha256_hash,
    sign_header,
    verify_signature,
    encrypt_payload,
    decrypt_payload,
    generate_session_key,
    load_private_key,
    load_public_key,
)
from pathlib import Path
import tempfile
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization


@pytest.fixture
def test_key_pair():
    """Generate test ECDSA key pair."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    
    # Save to temp files
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pem') as f:
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        f.write(private_pem)
        private_path = f.name
    
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pem') as f:
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        f.write(public_pem)
        public_path = f.name
    
    yield private_key, public_key, private_path, public_path
    
    # Cleanup
    Path(private_path).unlink()
    Path(public_path).unlink()


class TestEnvelopeSchema:
    """Test semantic envelope schema and serialization."""
    
    def test_envelope_header_creation(self):
        """Create envelope header with all fields."""
        header = SemanticEnvelopeHeader(
            intent_class=IntentClass.USER_TURN.value,
            sensitivity=SensitivityLevel.LOW.value,
            token_estimate=100,
            agent_depth=0,
            session_id="session-123",
            turn_index=1,
            timestamp=1234567890000,
            routing_hint="best-available",
            integrity_hash="abc123def456",
            envelope_sig="",
        )
        
        assert header.intent_class == IntentClass.USER_TURN.value
        assert header.sensitivity == SensitivityLevel.LOW.value
        assert header.token_estimate == 100
    
    def test_header_to_canonical_json(self):
        """Serialize header to canonical JSON."""
        header = SemanticEnvelopeHeader(
            intent_class=IntentClass.USER_TURN.value,
            sensitivity=SensitivityLevel.LOW.value,
            token_estimate=100,
            agent_depth=0,
            session_id="session-123",
            turn_index=1,
            timestamp=1234567890000,
            routing_hint="best-available",
            integrity_hash="abc123def456",
            envelope_sig="test-sig",
        )
        
        canonical = header.to_canonical_json()
        assert isinstance(canonical, bytes)
        
        # Verify it's valid JSON without the signature
        data = json.loads(canonical.decode('utf-8'))
        assert "envelope_sig" not in data
        assert data["intent_class"] == IntentClass.USER_TURN.value
    
    def test_header_to_json_with_signature(self):
        """Serialize header to JSON with signature."""
        header = SemanticEnvelopeHeader(
            intent_class=IntentClass.USER_TURN.value,
            sensitivity=SensitivityLevel.LOW.value,
            token_estimate=100,
            agent_depth=0,
            session_id="session-123",
            turn_index=1,
            timestamp=1234567890000,
            routing_hint="best-available",
            integrity_hash="abc123def456",
            envelope_sig="test-sig-value",
        )
        
        json_str = header.to_json()
        data = json.loads(json_str)
        assert data["envelope_sig"] == "test-sig-value"


class TestRoutingHint:
    """Test routing hint derivation."""
    
    def test_routing_hint_domestic_only_for_high_pii(self):
        """High PII sets routing hint to domestic-only."""
        hint = derive_routing_hint(
            IntentClass.USER_TURN,
            SensitivityLevel.HIGH_PII
        )
        assert hint == "domestic-only"
    
    def test_routing_hint_sandbox_for_tool_call(self):
        """Tool call sets routing hint to sandbox-cluster."""
        hint = derive_routing_hint(
            IntentClass.TOOL_CALL,
            SensitivityLevel.LOW
        )
        assert hint == "sandbox-cluster"
    
    def test_routing_hint_block_for_jailbreak(self):
        """Jailbreak candidate sets routing hint to block."""
        hint = derive_routing_hint(
            IntentClass.JAILBREAK_CANDIDATE,
            SensitivityLevel.LOW
        )
        assert hint == "block"
    
    def test_routing_hint_best_available_default(self):
        """Default routing hint is best-available."""
        hint = derive_routing_hint(
            IntentClass.USER_TURN,
            SensitivityLevel.LOW
        )
        assert hint == "best-available"


class TestCryptography:
    """Test cryptographic functions."""
    
    def test_sha256_hash(self):
        """Generate SHA-256 hash."""
        data = b"test data"
        hash_hex = generate_sha256_hash(data)
        
        # Verify hash is hex string and correct length
        assert isinstance(hash_hex, str)
        assert len(hash_hex) == 64  # SHA-256 = 256 bits = 64 hex chars
        
        # Verify hash value
        expected = hashlib.sha256(data).hexdigest()
        assert hash_hex == expected
    
    def test_ecdsa_signing(self, test_key_pair):
        """Sign and verify ECDSA signature."""
        private_key, public_key, _, _ = test_key_pair
        
        data = b"test data to sign"
        signature_hex = sign_header(data, private_key)
        
        assert isinstance(signature_hex, str)
        assert len(signature_hex) > 0
        
        # Verify signature
        is_valid = verify_signature(data, signature_hex, public_key)
        assert is_valid
    
    def test_ecdsa_verification_fails_for_tampered_data(self, test_key_pair):
        """Verification fails if data is tampered."""
        private_key, public_key, _, _ = test_key_pair
        
        data = b"original data"
        signature_hex = sign_header(data, private_key)
        
        # Try to verify with different data
        tampered_data = b"tampered data"
        is_valid = verify_signature(tampered_data, signature_hex, public_key)
        assert not is_valid
    
    def test_aes256_encryption_and_decryption(self):
        """Encrypt and decrypt with AES-256-GCM."""
        key = generate_session_key()  # 32 bytes
        plaintext = b"This is secret data to encrypt"
        
        # Encrypt
        ciphertext, iv, _ = encrypt_payload(plaintext, key)
        
        # Verify IV is 12 bytes
        assert len(iv) == 12
        
        # Extract auth tag (last 16 bytes of ciphertext)
        auth_tag = ciphertext[-16:]
        encrypted_payload = ciphertext[:-16]
        
        # Decrypt by reconstructing ciphertext with tag
        ciphertext_with_tag = encrypted_payload + auth_tag
        decrypted = decrypt_payload(ciphertext_with_tag, iv, key)
        
        assert decrypted == plaintext
    
    def test_aes256_encryption_produces_different_ciphertext(self):
        """Each encryption produces different ciphertext (due to random IV)."""
        key = generate_session_key()
        plaintext = b"Same plaintext"
        
        ciphertext1, iv1, _ = encrypt_payload(plaintext, key)
        ciphertext2, iv2, _ = encrypt_payload(plaintext, key)
        
        # IVs should be different
        assert iv1 != iv2
        
        # Ciphertexts should be different (due to different IVs)
        assert ciphertext1 != ciphertext2


class TestEnvelopeBuilding:
    """Test envelope building process."""
    
    def test_envelope_build_complete(self, test_key_pair):
        """Build complete envelope with all fields populated."""
        private_key, public_key, _, _ = test_key_pair
        
        request_body = {
            "messages": [{"role": "user", "content": "Hello, world!"}],
            "model": "gpt-4",
        }
        request_bytes = json.dumps(request_body).encode('utf-8')
        
        aes_key = generate_session_key()
        envelope = build_envelope(
            original_request_body=request_bytes,
            session_id="test-session-123",
            turn_index=1,
            agent_depth=0,
            aes_key=aes_key,
            private_key=private_key,
            tier2_threshold=0.75,
            token_estimate_method="heuristic",
        )
        
        # Verify all fields are populated
        assert envelope.header.intent_class == IntentClass.USER_TURN.value
        assert envelope.header.session_id == "test-session-123"
        assert envelope.header.turn_index == 1
        assert envelope.header.agent_depth == 0
        assert len(envelope.header.integrity_hash) == 64  # SHA-256 hex
        assert len(envelope.header.envelope_sig) > 0
        assert len(envelope.encrypted_payload) > 0
        assert len(envelope.iv) == 12
        assert len(envelope.auth_tag) == 16
    
    def test_envelope_integrity_hash_matches_original(self, test_key_pair):
        """Integrity hash matches SHA-256 of original request."""
        private_key, _, _, _ = test_key_pair
        
        request_body = {"messages": [{"role": "user", "content": "Test"}]}
        request_bytes = json.dumps(request_body).encode('utf-8')
        
        aes_key = generate_session_key()
        envelope = build_envelope(
            original_request_body=request_bytes,
            session_id="test-session",
            turn_index=0,
            agent_depth=0,
            aes_key=aes_key,
            private_key=private_key,
        )
        
        expected_hash = hashlib.sha256(request_bytes).hexdigest()
        assert envelope.header.integrity_hash == expected_hash
    
    def test_envelope_signature_verifiable(self, test_key_pair):
        """Envelope signature can be verified with public key."""
        private_key, public_key, _, _ = test_key_pair
        
        request_body = {"messages": [{"role": "user", "content": "Verify me"}]}
        request_bytes = json.dumps(request_body).encode('utf-8')
        
        aes_key = generate_session_key()
        envelope = build_envelope(
            original_request_body=request_bytes,
            session_id="test-session",
            turn_index=0,
            agent_depth=0,
            aes_key=aes_key,
            private_key=private_key,
        )
        
        # Verify the signature
        header_canonical = envelope.header.to_canonical_json()
        is_valid = verify_signature(
            header_canonical,
            envelope.header.envelope_sig,
            public_key
        )
        assert is_valid
    
    def test_envelope_payload_decryptable(self, test_key_pair):
        """Encrypted payload can be decrypted to original."""
        private_key, _, _, _ = test_key_pair
        
        request_body = {"messages": [{"role": "user", "content": "Encrypt me"}]}
        request_bytes = json.dumps(request_body).encode('utf-8')
        
        aes_key = generate_session_key()
        envelope = build_envelope(
            original_request_body=request_bytes,
            session_id="test-session",
            turn_index=0,
            agent_depth=0,
            aes_key=aes_key,
            private_key=private_key,
        )
        
        # Decrypt the payload
        ciphertext_with_tag = envelope.encrypted_payload + envelope.auth_tag
        decrypted = decrypt_payload(ciphertext_with_tag, envelope.iv, aes_key)
        
        assert decrypted == request_bytes
