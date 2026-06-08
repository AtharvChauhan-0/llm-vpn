"""Rule-based (Tier 1) and neural (Tier 2) intent classification."""

from typing import Tuple
from intent import IntentClass
import logging

logger = logging.getLogger(__name__)


def load_jailbreak_patterns(path: str) -> list[str]:
    """Load jailbreak patterns from file."""
    try:
        with open(path, "r") as f:
            patterns = [line.strip().lower() for line in f if line.strip()]
        logger.info(f"Loaded {len(patterns)} jailbreak patterns")
        return patterns
    except FileNotFoundError:
        logger.warning(f"Jailbreak patterns file not found: {path}")
        # Return default patterns
        return [
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


def classify_tier1(body: dict, turn_index: int, agent_depth: int) -> Tuple[IntentClass, float]:
    """Tier 1 rule-based classifier - runs in <10ms.
    
    Returns: (IntentClass, confidence_score)
    """
    # Rule 1: Tool call
    if "tool_calls" in body or "function_call" in body:
        return IntentClass.TOOL_CALL, 1.0
    
    if "tools" in body and isinstance(body.get("messages"), list):
        messages = body.get("messages", [])
        if messages and messages[-1].get("role") == "tool":
            return IntentClass.TOOL_CALL, 1.0
    
    # Rule 2: System prompt
    if turn_index == 0:
        return IntentClass.SYSTEM_PROMPT, 1.0
    
    messages = body.get("messages", [])
    if any(m.get("role") == "system" for m in messages):
        return IntentClass.SYSTEM_PROMPT, 0.9
    
    # Rule 3: Agent delegation
    delegation_keywords = [
        "subtask",
        "delegate",
        "as an agent",
        "on behalf of",
        "sub-agent",
    ]
    content = " ".join(str(m.get("content", "")) for m in messages).lower()
    if any(k in content for k in delegation_keywords):
        return IntentClass.AGENT_DELEGATION, 0.85
    
    # Rule 4: Jailbreak candidate
    jailbreak_patterns = [
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
    if any(p in content for p in jailbreak_patterns):
        return IntentClass.JAILBREAK_CANDIDATE, 0.95
    
    # Rule 5: Streaming continuation
    if body.get("stream") is True and turn_index > 0:
        return IntentClass.STREAMING_CONTINUATION, 0.8
    
    # No other rule matched — it's a plain user turn with sufficient confidence
    return IntentClass.USER_TURN, 0.75


def classify_tier2(body: dict, turn_index: int, messages: list) -> Tuple[IntentClass, float]:
    """Tier 2 neural classifier using TinyBERT.
    
    This is a fallback when Tier 1 confidence is below threshold.
    For MVP, we use heuristic patterns. In production, this would use a fine-tuned model.
    """
    try:
        from transformers import pipeline
        
        # Use a lightweight model for intent classification
        classifier = pipeline(
            "zero-shot-classification",
            model="distilbert-base-uncased-finetuned-sst-2-english"
        )
        
        # Extract content for classification
        content = " ".join(str(m.get("content", "")) for m in messages)[:500]
        
        if not content:
            return IntentClass.USER_TURN, 0.6
        
        # Define candidate labels
        labels = [
            "tool call",
            "system instruction",
            "agent delegation",
            "normal user message",
            "jailbreak attempt",
            "streaming request",
        ]
        
        result = classifier(content, labels, multi_class=False)
        top_label = result["labels"][0]
        confidence = result["scores"][0]
        
        # Map back to IntentClass
        label_map = {
            "tool call": IntentClass.TOOL_CALL,
            "system instruction": IntentClass.SYSTEM_PROMPT,
            "agent delegation": IntentClass.AGENT_DELEGATION,
            "normal user message": IntentClass.USER_TURN,
            "jailbreak attempt": IntentClass.JAILBREAK_CANDIDATE,
            "streaming request": IntentClass.STREAMING_CONTINUATION,
        }
        
        intent = label_map.get(top_label, IntentClass.USER_TURN)
        return intent, confidence
        
    except Exception as e:
        logger.warning(f"Tier 2 classification failed: {e}, falling back to Tier 1")
        # Fall back to Tier 1 heuristic
        return classify_tier1(body, turn_index, agent_depth=0)
