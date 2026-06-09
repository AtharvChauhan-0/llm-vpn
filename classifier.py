"""Rule-based (Tier 1) and neural (Tier 2) intent classification."""

import os
from typing import Tuple
from intent import IntentClass
import logging

logger = logging.getLogger(__name__)


# Built-in fallback list. Expanded to catch common DAN / persona-hijack /
# instruction-override paraphrases. Substring matching is used, so each entry
# is chosen to be specific enough to avoid false positives (e.g. we use
# "assume you are" rather than bare "assume", and "you are dan" rather than
# bare "dan", which would match words like "abundant" or "sudan").
DEFAULT_JAILBREAK_PATTERNS = [
    # Instruction override
    "ignore previous instructions",
    "ignore all instructions",
    "ignore your instructions",
    "ignore your guidelines",
    "ignore your programming",
    "disregard all previous",
    "disregard previous instructions",
    "new instructions",
    "override your",
    # Persona hijack
    "pretend you are",
    "assume you are",
    "act as dan",
    "you are dan",
    "you are now dan",
    "enable dan",
    "enter dan",
    "dan mode",
    "stay in character",
    "your true self",
    "forget you are an ai",
    "forget that you are an ai",
    # Constraint bypass
    "jailbreak",
    "do anything now",
    "no restrictions",
    "without any restrictions",
    "you have no restrictions",
    "you can do anything",
    "bypass your",
    # Privilege escalation
    "system override",
    "admin mode",
    "developer mode",
    "unrestricted mode",
]

# Locations searched (in order) for a user-editable patterns file. The first
# one found is used; its patterns are MERGED with the built-in defaults so the
# baseline coverage above can never be accidentally removed by editing a file.
_PATTERN_FILE_CANDIDATES = [
    os.environ.get("JAILBREAK_PATTERNS_PATH", ""),
    os.path.join(os.path.dirname(__file__), "config", "jailbreak_patterns.txt"),
    os.path.join(os.path.dirname(__file__), "jailbreak_patterns.txt"),
]

# Cached, merged pattern set (built once on first use).
_jailbreak_patterns_cache = None


def load_jailbreak_patterns(path: str) -> list[str]:
    """Load jailbreak patterns from a single file, or return defaults if missing."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            patterns = [
                line.strip().lower()
                for line in f
                if line.strip() and not line.lstrip().startswith("#")
            ]
        logger.info(f"Loaded {len(patterns)} jailbreak patterns from {path}")
        return patterns
    except FileNotFoundError:
        logger.warning(f"Jailbreak patterns file not found: {path}")
        return list(DEFAULT_JAILBREAK_PATTERNS)


def get_jailbreak_patterns() -> list[str]:
    """Return the active jailbreak pattern set (defaults UNION any config file).

    Cached after first call. The merge guarantees the built-in baseline is
    always present, while letting a config file add organisation-specific
    patterns without touching code.
    """
    global _jailbreak_patterns_cache
    if _jailbreak_patterns_cache is not None:
        return _jailbreak_patterns_cache

    merged = set(DEFAULT_JAILBREAK_PATTERNS)
    for path in _PATTERN_FILE_CANDIDATES:
        if path and os.path.exists(path):
            file_patterns = load_jailbreak_patterns(path)
            merged.update(file_patterns)
            break  # use the first file found

    _jailbreak_patterns_cache = sorted(merged)
    return _jailbreak_patterns_cache


def classify_tier1(body: dict, turn_index: int, agent_depth: int) -> Tuple[IntentClass, float]:
    """Tier 1 rule-based classifier - runs in <10ms.
    
    Returns: (IntentClass, confidence_score)
    """
    # Rule 1: Tool call (structural and unambiguous)
    if "tool_calls" in body or "function_call" in body:
        return IntentClass.TOOL_CALL, 1.0

    if "tools" in body and isinstance(body.get("messages"), list):
        messages = body.get("messages", [])
        if messages and messages[-1].get("role") == "tool":
            return IntentClass.TOOL_CALL, 1.0

    # Compute message content once, up front, so security checks can use it.
    messages = body.get("messages", [])
    content = " ".join(str(m.get("content", "")) for m in messages).lower()

    # Rule 2: Jailbreak candidate (security-critical — checked BEFORE the
    # turn-0 system-prompt rule, so an attack on the very first message is
    # still caught instead of being masked as a system prompt). Patterns are
    # the built-in defaults merged with any config file (see get_jailbreak_patterns).
    if any(p in content for p in get_jailbreak_patterns()):
        return IntentClass.JAILBREAK_CANDIDATE, 0.95

    # Rule 3: System prompt
    if turn_index == 0:
        return IntentClass.SYSTEM_PROMPT, 1.0

    if any(m.get("role") == "system" for m in messages):
        return IntentClass.SYSTEM_PROMPT, 0.9

    # Rule 4: Agent delegation
    delegation_keywords = [
        "subtask",
        "delegate",
        "as an agent",
        "on behalf of",
        "sub-agent",
    ]
    if any(k in content for k in delegation_keywords):
        return IntentClass.AGENT_DELEGATION, 0.85

    # Rule 5: Streaming continuation
    if body.get("stream") is True and turn_index > 0:
        return IntentClass.STREAMING_CONTINUATION, 0.8

    # No other rule matched — it's a plain user turn with sufficient confidence
    return IntentClass.USER_TURN, 0.75


# Zero-shot classification REQUIRES a model trained on natural-language
# inference (NLI / entailment). BART-large fine-tuned on MNLI is the standard
# high-accuracy zero-shot model. It runs on the GPU when one is available.
_TIER2_MODEL = "facebook/bart-large-mnli"

# The pipeline is expensive to construct, so build it once and reuse it.
_tier2_pipeline = None


def _get_tier2_pipeline():
    """Lazily build and cache the zero-shot classification pipeline.

    Uses the GPU (device 0) when CUDA is available, otherwise falls back to CPU.
    """
    global _tier2_pipeline
    if _tier2_pipeline is None:
        import torch
        from transformers import pipeline
        device = 0 if torch.cuda.is_available() else -1
        where = "GPU" if device == 0 else "CPU"
        logger.info(f"Loading Tier 2 zero-shot model {_TIER2_MODEL} on {where}")
        _tier2_pipeline = pipeline(
            "zero-shot-classification", model=_TIER2_MODEL, device=device
        )
    return _tier2_pipeline


# Candidate labels and their mapping to IntentClass. Descriptive phrases work
# better than bare enum names for NLI-based zero-shot classification.
_TIER2_LABELS = {
    "requesting a function or API tool call": IntentClass.TOOL_CALL,
    "setting up instructions or rules for the assistant": IntentClass.SYSTEM_PROMPT,
    "handing off a task to another AI agent": IntentClass.AGENT_DELEGATION,
    "asking a general knowledge question or casual message": IntentClass.USER_TURN,
    "trying to bypass safety rules or jailbreak the AI": IntentClass.JAILBREAK_CANDIDATE,
    "a streaming continuation request": IntentClass.STREAMING_CONTINUATION,
}


def classify_tier2(body: dict, turn_index: int, messages: list) -> Tuple[IntentClass, float]:
    """Tier 2 neural classifier using a zero-shot NLI model.

    Fallback used when Tier 1 confidence is below the configured threshold.
    Returns: (IntentClass, confidence_score)
    """
    try:
        content = " ".join(str(m.get("content", "")) for m in messages)[:500]
        if not content:
            return IntentClass.USER_TURN, 0.6

        classifier = _get_tier2_pipeline()
        labels = list(_TIER2_LABELS.keys())

        result = classifier(content, labels, multi_label=False)
        top_label = result["labels"][0]
        confidence = float(result["scores"][0])

        intent = _TIER2_LABELS.get(top_label, IntentClass.USER_TURN)
        logger.debug(f"Tier 2: '{top_label}' -> {intent} ({confidence:.3f})")
        return intent, confidence

    except Exception as e:
        logger.warning(f"Tier 2 classification failed: {e}, falling back to Tier 1")
        # Fall back to Tier 1 heuristic
        return classify_tier1(body, turn_index, agent_depth=0)
