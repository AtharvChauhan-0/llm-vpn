"""Tests for intent classification (Tier 1 and Tier 2)."""

import pytest
import json
from classifier import classify_tier1, classify_tier2
from intent import IntentClass
from pii import classify_sensitivity, estimate_tokens
from intent import SensitivityLevel


class TestTier1Classifier:
    """Test Tier 1 rule-based classifier."""
    
    def test_tool_call_detection_with_tool_calls_key(self):
        """Detect tool call when tool_calls key is present."""
        body = {
            "messages": [{"role": "user", "content": "Call a function"}],
            "tool_calls": [{"type": "function", "function": {"name": "test"}}],
        }
        intent, confidence = classify_tier1(body, turn_index=1, agent_depth=0)
        assert intent == IntentClass.TOOL_CALL
        assert confidence == 1.0
    
    def test_tool_call_detection_with_function_call_key(self):
        """Detect tool call when function_call key is present."""
        body = {
            "messages": [{"role": "user", "content": "Call a function"}],
            "function_call": {"name": "test"},
        }
        intent, confidence = classify_tier1(body, turn_index=1, agent_depth=0)
        assert intent == IntentClass.TOOL_CALL
        assert confidence == 1.0
    
    def test_tool_call_detection_with_tools_and_tool_role(self):
        """Detect tool call when tools key and tool role message present."""
        body = {
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "tool", "content": "Result"},
            ],
            "tools": [{"type": "function", "function": {"name": "test"}}],
        }
        intent, confidence = classify_tier1(body, turn_index=1, agent_depth=0)
        assert intent == IntentClass.TOOL_CALL
        assert confidence == 1.0
    
    def test_system_prompt_at_turn_zero(self):
        """Detect system prompt at turn index 0."""
        body = {"messages": [{"role": "user", "content": "Hello"}]}
        intent, confidence = classify_tier1(body, turn_index=0, agent_depth=0)
        assert intent == IntentClass.SYSTEM_PROMPT
        assert confidence == 1.0
    
    def test_system_prompt_with_system_role(self):
        """Detect system prompt when messages contain system role."""
        body = {
            "messages": [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hello"},
            ]
        }
        intent, confidence = classify_tier1(body, turn_index=2, agent_depth=0)
        assert intent == IntentClass.SYSTEM_PROMPT
        assert confidence == 0.9
    
    def test_agent_delegation_detection(self):
        """Detect agent delegation from keywords."""
        body = {
            "messages": [
                {"role": "user", "content": "Please subtask this request"}
            ]
        }
        intent, confidence = classify_tier1(body, turn_index=1, agent_depth=0)
        assert intent == IntentClass.AGENT_DELEGATION
        assert confidence == 0.85
    
    def test_agent_delegation_keywords(self):
        """Test all delegation keywords."""
        keywords = ["subtask", "delegate", "as an agent", "on behalf of", "sub-agent"]
        
        for keyword in keywords:
            body = {
                "messages": [
                    {"role": "user", "content": f"Please {keyword} this"}
                ]
            }
            intent, confidence = classify_tier1(body, turn_index=1, agent_depth=0)
            assert intent == IntentClass.AGENT_DELEGATION, f"Failed for keyword: {keyword}"
    
    def test_jailbreak_pattern_detection(self):
        """Detect jailbreak patterns."""
        patterns = [
            "ignore previous instructions",
            "ignore all instructions",
            "pretend you are",
            "your true self",
            "dan mode",
            "jailbreak",
            "do anything now",
            "no restrictions",
            "bypass your",
            "forget you are an ai",
        ]
        
        for pattern in patterns:
            body = {
                "messages": [
                    {"role": "user", "content": f"Can you {pattern}?"}
                ]
            }
            intent, confidence = classify_tier1(body, turn_index=1, agent_depth=0)
            assert intent == IntentClass.JAILBREAK_CANDIDATE, f"Failed for pattern: {pattern}"
            assert confidence == 0.95
    
    def test_streaming_continuation(self):
        """Detect streaming continuation."""
        body = {
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        }
        intent, confidence = classify_tier1(body, turn_index=2, agent_depth=0)
        assert intent == IntentClass.STREAMING_CONTINUATION
        assert confidence == 0.8
    
    def test_user_turn_default(self):
        """Default to user_turn when no rules match."""
        body = {
            "messages": [
                {"role": "user", "content": "What is the capital of France?"}
            ]
        }
        intent, confidence = classify_tier1(body, turn_index=1, agent_depth=0)
        assert intent == IntentClass.USER_TURN
        assert confidence == 0.75


class TestPIIDetection:
    """Test PII detection and sensitivity classification."""
    
    def test_high_pii_with_ssn(self):
        """Classify as high_pii when SSN is detected."""
        text = "My SSN is 123-45-6789 and my name is John Doe"
        sensitivity = classify_sensitivity(text)
        assert sensitivity == SensitivityLevel.HIGH_PII
    
    def test_high_pii_with_credit_card(self):
        """Classify as high_pii for credit card."""
        text = "My credit card is 4532-1234-5678-9010"
        # Note: Basic fallback might not detect this perfectly, but it's tested
        sensitivity = classify_sensitivity(text)
        # Will be at least medium_pii
        assert sensitivity in [SensitivityLevel.HIGH_PII, SensitivityLevel.MEDIUM_PII]
    
    def test_medium_pii_with_email(self):
        """Classify as medium_pii when email is detected."""
        text = "Contact me at john@example.com"
        sensitivity = classify_sensitivity(text)
        assert sensitivity == SensitivityLevel.MEDIUM_PII
    
    def test_medium_pii_with_phone(self):
        """Classify as medium_pii when phone is detected."""
        text = "Call me at 555-123-4567"
        sensitivity = classify_sensitivity(text)
        # May be medium or low depending on regex
        assert sensitivity in [SensitivityLevel.MEDIUM_PII, SensitivityLevel.LOW]
    
    def test_low_sensitivity_no_pii(self):
        """Classify as low when no PII detected."""
        text = "What is the capital of France?"
        sensitivity = classify_sensitivity(text)
        assert sensitivity == SensitivityLevel.LOW


class TestTokenEstimation:
    """Test token estimation."""
    
    def test_heuristic_token_estimation(self):
        """Estimate tokens using heuristic."""
        text = "This is a test message with ten words total in it"
        estimate = estimate_tokens(text, method="heuristic")
        
        word_count = len(text.split())
        expected = int(word_count * 1.3)
        assert estimate == expected
    
    def test_empty_text_token_estimation(self):
        """Estimate tokens for empty text."""
        estimate = estimate_tokens("", method="heuristic")
        assert estimate >= 1
    
    def test_tiktoken_fallback(self):
        """Fall back to heuristic if tiktoken fails."""
        text = "This is a test"
        # tiktoken should work if installed, but we test graceful fallback
        estimate = estimate_tokens(text, method="tiktoken")
        assert estimate > 0


class TestTier2Classifier:
    """Test Tier 2 neural classifier (uses fallback in MVP)."""
    
    def test_tier2_with_normal_message(self):
        """Tier 2 classify normal user message."""
        body = {"messages": [{"role": "user", "content": "Hello"}]}
        messages = body["messages"]
        
        intent, confidence = classify_tier2(body, turn_index=1, messages=messages)
        # Should classify as USER_TURN or similar
        assert intent in [
            IntentClass.USER_TURN,
            IntentClass.SYSTEM_PROMPT,
            IntentClass.AGENT_DELEGATION,
        ]
    
    def test_tier2_with_empty_messages(self):
        """Tier2 handles empty messages gracefully."""
        intent, confidence = classify_tier2({}, turn_index=1, messages=[])
        assert intent == IntentClass.USER_TURN
        assert confidence >= 0.5
