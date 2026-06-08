"""PII detection and sensitivity classification using Presidio."""

from typing import Tuple, Set
from intent import SensitivityLevel
import logging

logger = logging.getLogger(__name__)


def detect_pii_entities(text: str, threshold: float = 0.6) -> Set[str]:
    """Detect PII entities in text using Presidio.
    
    Returns: set of entity types found (e.g., {"PERSON", "EMAIL_ADDRESS"})
    """
    try:
        from presidio_analyzer import AnalyzerEngine
        
        from presidio_analyzer.nlp_engine import NlpEngineProvider
        config = {"nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}]}
        provider = NlpEngineProvider(nlp_configuration=config)
        nlp_engine = provider.create_engine()
        analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
        results = analyzer.analyze(text, language="en")
        
        # Filter by score threshold and return entity types
        entities = set()
        for result in results:
            if result.score >= threshold:
                entities.add(result.entity_type)
        
        # Always also run regex fallback and merge — Presidio may miss some
        # formats that fail internal validation (e.g. non-Luhn CC numbers).
        entities |= _basic_pii_detection(text)
        return entities
    except Exception as e:
        logger.warning(f"Presidio analysis failed: {e}")
        return _basic_pii_detection(text)


def _basic_pii_detection(text: str) -> Set[str]:
    """Basic regex-based PII detection as fallback."""
    import re
    
    entities = set()
    text_lower = text.lower()
    
    # Simple patterns (not production-grade)
    if re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", text):
        entities.add("EMAIL_ADDRESS")
    
    if re.search(r"\b\d{3}-\d{2}-\d{4}\b", text):
        entities.add("US_SSN")
    
    if re.search(r"\b\d{10,}\b", text):
        entities.add("PHONE_NUMBER")

    # Credit card: 16-digit groups separated by spaces or dashes
    if re.search(r"\b(?:\d{4}[-\s]){3}\d{4}\b", text):
        entities.add("CREDIT_CARD")
    
    if re.search(r"\b[0-9]{1,5}\s+[A-Z][a-z]+(\s+[A-Z][a-z]+)*", text):
        entities.add("PERSON")
    
    return entities


def classify_sensitivity(text: str, threshold: float = 0.6) -> SensitivityLevel:
    """Classify text sensitivity based on PII detection.
    
    Returns: SensitivityLevel enum value
    """
    entities = detect_pii_entities(text, threshold)
    
    # High PII: dangerous combinations or highly sensitive types
    high_pii_indicators = {
        ("PERSON", "LOCATION"),  # person + location
        "CREDIT_CARD",
        "US_SSN",
        "PASSPORT",
        "MEDICAL_RECORD",
    }
    
    # Check for dangerous combinations
    for indicator in high_pii_indicators:
        if isinstance(indicator, tuple):
            if all(e in entities for e in indicator):
                return SensitivityLevel.HIGH_PII
        elif indicator in entities:
            return SensitivityLevel.HIGH_PII
    
    # Medium PII: standard PII types individually
    medium_pii_indicators = {
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "IP_ADDRESS",
        "PERSON",
    }
    
    if any(e in entities for e in medium_pii_indicators):
        return SensitivityLevel.MEDIUM_PII
    
    return SensitivityLevel.LOW


def estimate_tokens(text: str, method: str = "heuristic") -> int:
    """Estimate token count using heuristic or tiktoken.
    
    Args:
        text: string to estimate tokens for
        method: "heuristic" or "tiktoken"
    
    Returns: estimated token count
    """
    if method == "tiktoken":
        try:
            import tiktoken
            
            encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
            tokens = encoding.encode(text)
            return len(tokens)
        except Exception as e:
            logger.warning(f"Tiktoken estimation failed: {e}, falling back to heuristic")
    
    # Heuristic: word count * 1.3 (rough approximation)
    words = len(text.split())
    return max(1, int(words * 1.3))
