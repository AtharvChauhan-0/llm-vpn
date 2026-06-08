"""Session state management."""

from dataclasses import dataclass, field
import time
from intent import IntentClass


@dataclass
class SessionState:
    """Per-session state tracking."""
    session_id: str
    turn_index: int = 0
    agent_depth: int = 0
    aes_key: bytes = field(default_factory=bytes)
    created_at: int = field(default_factory=lambda: int(time.time()))
    last_active: int = field(default_factory=lambda: int(time.time()))
    intent_history: list[str] = field(default_factory=list)  # Last 10 intents
    
    def add_intent(self, intent):
        """Record intent in history (keep last 10). Accepts IntentClass or str."""
        value = intent.value if isinstance(intent, IntentClass) else str(intent)
        self.intent_history.append(value)
        if len(self.intent_history) > 10:
            self.intent_history.pop(0)
        self.last_active = int(time.time())
    
    def increment_turn(self):
        """Increment turn index and update last active."""
        self.turn_index += 1
        self.last_active = int(time.time())
    
    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if session has expired."""
        elapsed_seconds = int(time.time()) - self.last_active
        return elapsed_seconds > (timeout_minutes * 60)


class SessionManager:
    """Manage active sessions."""
    
    def __init__(self, timeout_minutes: int = 30):
        self.sessions: dict[str, SessionState] = {}
        self.timeout_minutes = timeout_minutes
    
    def get_or_create(self, session_id: str, aes_key: bytes) -> SessionState:
        """Get existing session or create new one."""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.increment_turn()
            return session
        
        session = SessionState(
            session_id=session_id,
            aes_key=aes_key,
        )
        self.sessions[session_id] = session
        return session
    
    def cleanup_expired(self) -> int:
        """Remove expired sessions and return count."""
        expired = [
            sid for sid, session in self.sessions.items()
            if session.is_expired(self.timeout_minutes)
        ]
        
        for sid in expired:
            del self.sessions[sid]
        
        return len(expired)
    
    def get_stats(self) -> dict:
        """Get current session statistics."""
        active = len(self.sessions)
        total_turns = sum(s.turn_index + 1 for s in self.sessions.values())
        avg_depth = sum(s.agent_depth for s in self.sessions.values()) / max(1, active)
        
        return {
            "active_sessions": active,
            "total_turns": total_turns,
            "avg_agent_depth": avg_depth,
        }
