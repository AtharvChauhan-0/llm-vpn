"""HTTP proxy implementation using mitmproxy."""

import hashlib
import json
import logging
from typing import Optional
from urllib.parse import urlparse
from intent import IntentClass, SensitivityLevel
from session import SessionManager
from builder import build_envelope
from crypto import generate_session_key, load_private_key

logger = logging.getLogger(__name__)


class LLMVPNProxy:
    """MITMPROXY addon for intercepting and enriching LLM API requests."""
    
    def __init__(
        self,
        llm_endpoints: list[str],
        private_key_path: str,
        session_timeout_minutes: int = 30,
        tier2_threshold: float = 0.75,
        token_estimate_method: str = "heuristic",
    ):
        self.llm_endpoints = llm_endpoints
        self.private_key = load_private_key(private_key_path)
        self.session_manager = SessionManager(timeout_minutes=session_timeout_minutes)
        self.tier2_threshold = tier2_threshold
        self.token_estimate_method = token_estimate_method
        
        # Statistics
        self.stats_total_requests = 0
        self.stats_intent_distribution = {}
        self.stats_sensitivity_distribution = {}
        self.stats_pii_hits = 0
        self.stats_total_tokens = 0
        
        logger.info("LLMVPNProxy initialized")
    
    def _should_intercept(self, host: str) -> bool:
        """Check if request should be intercepted."""
        for endpoint in self.llm_endpoints:
            if endpoint in host.lower():
                return True
        return False
    
    def _generate_session_id(self, client_address: str, timestamp: int) -> str:
        """Generate session ID from client IP and timestamp."""
        data = f"{client_address}:{timestamp}".encode("utf-8")
        return hashlib.sha256(data).hexdigest()[:16]
    
    def request(self, flow):
        """Handle outbound request interception."""
        host = flow.request.host
        
        # Check if this is an LLM endpoint
        if not self._should_intercept(host):
            return
        
        # Only intercept POST requests with JSON bodies
        if flow.request.method != "POST":
            return
        
        try:
            # Parse request body
            body = flow.request.get_content()
            if not body:
                return
            
            # Attempt to parse as JSON
            try:
                body_dict = json.loads(body)
            except json.JSONDecodeError:
                logger.warning("Request body is not JSON, skipping")
                return
            
            # Generate or retrieve session
            client_addr = flow.client_conn.peername[0] if flow.client_conn else "unknown"
            timestamp = int(flow.metadata.get("timestamp", 0) * 1000)
            session_id = self._generate_session_id(client_addr, timestamp)
            
            # Get or create session state
            aes_key = generate_session_key()
            session = self.session_manager.get_or_create(session_id, aes_key)
            
            # Build envelope
            envelope = build_envelope(
                original_request_body=body,
                session_id=session.session_id,
                turn_index=session.turn_index,
                agent_depth=session.agent_depth,
                aes_key=session.aes_key,
                private_key=self.private_key,
                tier2_threshold=self.tier2_threshold,
                token_estimate_method=self.token_estimate_method,
            )
            
            # Update session with intent history
            intent = IntentClass(envelope.header.intent_class)
            session.add_intent(intent)
            
            # Update statistics
            self.stats_total_requests += 1
            intent_key = envelope.header.intent_class
            self.stats_intent_distribution[intent_key] = (
                self.stats_intent_distribution.get(intent_key, 0) + 1
            )
            
            sensitivity_key = envelope.header.sensitivity
            self.stats_sensitivity_distribution[sensitivity_key] = (
                self.stats_sensitivity_distribution.get(sensitivity_key, 0) + 1
            )
            
            self.stats_total_tokens += envelope.header.token_estimate
            
            if sensitivity_key != SensitivityLevel.LOW.value:
                self.stats_pii_hits += 1
            
            # Attach X-Semantic-Envelope header
            envelope_header_b64 = envelope.header_as_base64()
            flow.request.headers["X-Semantic-Envelope"] = envelope_header_b64
            
            # Attach X-Envelope-Session header for correlation
            flow.request.headers["X-Envelope-Session"] = session.session_id
            
            # Replace request body with encrypted payload
            # Include IV and auth_tag in a wrapper structure
            encrypted_body = {
                "encrypted_payload": envelope.payload_as_base64(),
                "iv": envelope.iv_as_base64(),
                "auth_tag": envelope.auth_tag_as_base64(),
            }
            flow.request.text = json.dumps(encrypted_body)
            
            logger.info(
                f"Intercepted {host}: intent={intent}, session={session_id}, "
                f"turn={session.turn_index}"
            )
            
        except Exception as e:
            logger.error(f"Error processing request: {e}", exc_info=True)
    
    def response(self, flow):
        """Handle response from LLM endpoint."""
        host = flow.request.host
        
        if not self._should_intercept(host):
            return
        
        # Attach correlation header if we intercepted the request
        if "X-Envelope-Session" in flow.request.headers:
            session_id = flow.request.headers.get("X-Envelope-Session")
            flow.response.headers["X-Envelope-Session"] = session_id
            logger.debug(f"Response correlated to session {session_id}")
    
    def get_stats(self) -> dict:
        """Get aggregated statistics."""
        return {
            "total_requests": self.stats_total_requests,
            "intent_distribution": self.stats_intent_distribution,
            "sensitivity_distribution": self.stats_sensitivity_distribution,
            "pii_hits": self.stats_pii_hits,
            "avg_tokens_per_request": (
                self.stats_total_tokens / max(1, self.stats_total_requests)
            ),
            "session_stats": self.session_manager.get_stats(),
        }


# MITMPROXY addon instance
addons = [
    LLMVPNProxy(
        llm_endpoints=["api.openai.com", "api.anthropic.com"],
        private_key_path="./keys/private.pem",
    )
]
