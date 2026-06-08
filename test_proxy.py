"""Tests for proxy interception and session management."""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from session import SessionState, SessionManager
from interceptor import LLMVPNProxy
from crypto import generate_session_key
import time


class TestSessionManagement:
    """Test session state and management."""
    
    def test_session_state_creation(self):
        """Create session state."""
        aes_key = generate_session_key()
        session = SessionState(
            session_id="test-session-123",
            aes_key=aes_key,
        )
        
        assert session.session_id == "test-session-123"
        assert session.turn_index == 0
        assert session.agent_depth == 0
        assert len(session.aes_key) == 32
    
    def test_session_increment_turn(self):
        """Increment turn index."""
        session = SessionState(session_id="test")
        
        assert session.turn_index == 0
        session.increment_turn()
        assert session.turn_index == 1
        session.increment_turn()
        assert session.turn_index == 2
    
    def test_session_add_intent_history(self):
        """Add intent to history."""
        session = SessionState(session_id="test")
        
        session.add_intent("user_turn")
        assert "user_turn" in session.intent_history
        
        session.add_intent("tool_call")
        assert session.intent_history == ["user_turn", "tool_call"]
    
    def test_session_intent_history_limited_to_10(self):
        """Intent history limited to last 10."""
        session = SessionState(session_id="test")
        
        for i in range(15):
            session.add_intent(f"intent_{i}")
        
        assert len(session.intent_history) == 10
        assert "intent_5" in session.intent_history
        assert "intent_0" not in session.intent_history
    
    def test_session_expiration_check(self):
        """Check if session has expired."""
        session = SessionState(session_id="test")
        
        # Fresh session should not be expired
        assert not session.is_expired(timeout_minutes=30)
        
        # Manually set last_active to old time
        session.last_active = int(time.time()) - (31 * 60)  # 31 minutes ago
        assert session.is_expired(timeout_minutes=30)
    
    def test_session_manager_create_session(self):
        """Session manager creates new session."""
        manager = SessionManager(timeout_minutes=30)
        
        aes_key = generate_session_key()
        session = manager.get_or_create("session-123", aes_key)
        
        assert session.session_id == "session-123"
        assert session.turn_index == 0  # First turn
        assert "session-123" in manager.sessions
    
    def test_session_manager_retrieve_existing(self):
        """Session manager retrieves existing session."""
        manager = SessionManager(timeout_minutes=30)
        
        aes_key = generate_session_key()
        session1 = manager.get_or_create("session-123", aes_key)
        
        # Retrieve same session
        session2 = manager.get_or_create("session-123", aes_key)
        
        # Should be same object
        assert session1 is session2
        # Turn should have incremented
        assert session2.turn_index == 1
    
    def test_session_manager_increment_on_retrieve(self):
        """Turn index increments when retrieving existing session."""
        manager = SessionManager(timeout_minutes=30)
        
        aes_key = generate_session_key()
        session = manager.get_or_create("session-123", aes_key)
        assert session.turn_index == 0
        
        session = manager.get_or_create("session-123", aes_key)
        assert session.turn_index == 1
        
        session = manager.get_or_create("session-123", aes_key)
        assert session.turn_index == 2
    
    def test_session_manager_cleanup_expired(self):
        """Clean up expired sessions."""
        manager = SessionManager(timeout_minutes=1)
        
        aes_key = generate_session_key()
        session1 = manager.get_or_create("session-1", aes_key)
        session2 = manager.get_or_create("session-2", aes_key)
        
        # Expire session 1
        session1.last_active = int(time.time()) - (2 * 60)  # 2 minutes ago
        
        expired_count = manager.cleanup_expired()
        
        assert expired_count == 1
        assert "session-1" not in manager.sessions
        assert "session-2" in manager.sessions
    
    def test_session_manager_get_stats(self):
        """Get session statistics."""
        manager = SessionManager(timeout_minutes=30)
        
        aes_key = generate_session_key()
        session1 = manager.get_or_create("session-1", aes_key)
        session2 = manager.get_or_create("session-2", aes_key)
        
        # Make some turns
        manager.get_or_create("session-1", aes_key)
        manager.get_or_create("session-1", aes_key)
        
        stats = manager.get_stats()
        
        assert stats["active_sessions"] == 2
        assert stats["total_turns"] >= 3


class TestProxyInterception:
    """Test proxy request interception."""
    
    def test_proxy_initialization(self):
        """Initialize proxy."""
        proxy = LLMVPNProxy(
            llm_endpoints=["api.openai.com"],
            private_key_path="./keys/private.pem",
        )
        
        assert "api.openai.com" in proxy.llm_endpoints
        assert proxy.stats_total_requests == 0
    
    def test_should_intercept_openai_endpoint(self):
        """Should intercept OpenAI endpoint."""
        proxy = LLMVPNProxy(
            llm_endpoints=["api.openai.com"],
            private_key_path="./keys/private.pem",
        )
        
        assert proxy._should_intercept("api.openai.com")
        assert proxy._should_intercept("v1.api.openai.com")
        assert not proxy._should_intercept("example.com")
    
    def test_should_intercept_anthropic_endpoint(self):
        """Should intercept Anthropic endpoint."""
        proxy = LLMVPNProxy(
            llm_endpoints=["api.anthropic.com"],
            private_key_path="./keys/private.pem",
        )
        
        assert proxy._should_intercept("api.anthropic.com")
        assert not proxy._should_intercept("example.com")
    
    def test_session_id_generation(self):
        """Generate session ID from client address and timestamp."""
        proxy = LLMVPNProxy(
            llm_endpoints=["api.openai.com"],
            private_key_path="./keys/private.pem",
        )
        
        session_id1 = proxy._generate_session_id("192.168.1.1", 1000000)
        session_id2 = proxy._generate_session_id("192.168.1.1", 1000000)
        session_id3 = proxy._generate_session_id("192.168.1.2", 1000000)
        
        # Same client and timestamp should produce same ID
        assert session_id1 == session_id2
        
        # Different client should produce different ID
        assert session_id1 != session_id3
        
        # Should be 16 characters (SHA256 first 16 chars)
        assert len(session_id1) == 16
    
    def test_proxy_get_stats_initial(self):
        """Get initial proxy statistics."""
        proxy = LLMVPNProxy(
            llm_endpoints=["api.openai.com"],
            private_key_path="./keys/private.pem",
        )
        
        stats = proxy.get_stats()
        
        assert stats["total_requests"] == 0
        assert stats["pii_hits"] == 0
        assert stats["avg_tokens_per_request"] == 0


class TestProxyStatistics:
    """Test proxy statistics tracking."""
    
    def test_stats_intent_distribution(self):
        """Track intent distribution."""
        proxy = LLMVPNProxy(
            llm_endpoints=["api.openai.com"],
            private_key_path="./keys/private.pem",
        )
        
        # Simulate some requests
        proxy.stats_intent_distribution["user_turn"] = 5
        proxy.stats_intent_distribution["tool_call"] = 2
        
        stats = proxy.get_stats()
        
        assert stats["intent_distribution"]["user_turn"] == 5
        assert stats["intent_distribution"]["tool_call"] == 2
    
    def test_stats_sensitivity_distribution(self):
        """Track sensitivity distribution."""
        proxy = LLMVPNProxy(
            llm_endpoints=["api.openai.com"],
            private_key_path="./keys/private.pem",
        )
        
        proxy.stats_sensitivity_distribution["low"] = 10
        proxy.stats_sensitivity_distribution["high_pii"] = 1
        
        stats = proxy.get_stats()
        
        assert stats["sensitivity_distribution"]["low"] == 10
        assert stats["sensitivity_distribution"]["high_pii"] == 1
    
    def test_stats_pii_hits_tracking(self):
        """Track PII hits."""
        proxy = LLMVPNProxy(
            llm_endpoints=["api.openai.com"],
            private_key_path="./keys/private.pem",
        )
        
        proxy.stats_total_requests = 100
        proxy.stats_pii_hits = 5
        
        stats = proxy.get_stats()
        
        assert stats["pii_hits"] == 5
    
    def test_stats_average_tokens(self):
        """Calculate average tokens per request."""
        proxy = LLMVPNProxy(
            llm_endpoints=["api.openai.com"],
            private_key_path="./keys/private.pem",
        )
        
        proxy.stats_total_requests = 10
        proxy.stats_total_tokens = 1000
        
        stats = proxy.get_stats()
        
        assert stats["avg_tokens_per_request"] == 100.0
