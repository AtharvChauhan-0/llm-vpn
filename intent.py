"""Intent class and sensitivity level definitions."""

from enum import Enum
from dataclasses import dataclass


class IntentClass(str, Enum):
    """Classification of LLM request intent."""
    TOOL_CALL = "tool_call"
    SYSTEM_PROMPT = "system_prompt"
    AGENT_DELEGATION = "agent_delegation"
    USER_TURN = "user_turn"
    JAILBREAK_CANDIDATE = "jailbreak_candidate"
    STREAMING_CONTINUATION = "streaming_continuation"


class SensitivityLevel(str, Enum):
    """PII sensitivity classification."""
    HIGH_PII = "high_pii"
    MEDIUM_PII = "medium_pii"
    LOW = "low"


@dataclass
class TokenEstimate:
    """Token count estimate with heuristic and fallback."""
    heuristic_count: int  # word_count * 1.3
    accurate_count: int  # tiktoken result if available
    method: str  # "heuristic" or "tiktoken"
