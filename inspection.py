"""Inspection API for session monitoring and statistics."""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import logging
from session import SessionManager
from interceptor import LLMVPNProxy

logger = logging.getLogger(__name__)

app = FastAPI(title="LLM-VPN Inspection API")


class InspectionAPI:
    """REST API for inspecting VPN state."""
    
    def __init__(self, proxy: LLMVPNProxy):
        self.proxy = proxy
    
    def setup_routes(self, app: FastAPI):
        """Register routes on FastAPI app."""
        
        @app.get("/sessions")
        async def list_sessions():
            """List all active sessions."""
            sessions = []
            for sid, session in self.proxy.session_manager.sessions.items():
                sessions.append({
                    "session_id": session.session_id,
                    "turn_index": session.turn_index,
                    "agent_depth": session.agent_depth,
                    "created_at": session.created_at,
                    "last_active": session.last_active,
                    "intent_history": session.intent_history[-10:],
                })
            return {"sessions": sessions, "count": len(sessions)}
        
        @app.get("/sessions/{session_id}")
        async def get_session(session_id: str):
            """Get details of a specific session."""
            session = self.proxy.session_manager.sessions.get(session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            
            return {
                "session_id": session.session_id,
                "turn_index": session.turn_index,
                "agent_depth": session.agent_depth,
                "created_at": session.created_at,
                "last_active": session.last_active,
                "intent_history": session.intent_history,
                "is_expired": session.is_expired(),
            }
        
        @app.get("/stats")
        async def get_stats():
            """Get aggregated statistics."""
            stats = self.proxy.get_stats()
            
            # Clean up expired sessions periodically
            expired_count = self.proxy.session_manager.cleanup_expired()
            if expired_count > 0:
                logger.info(f"Cleaned up {expired_count} expired sessions")
            
            return {
                "statistics": stats,
                "cleanup": {
                    "expired_sessions_removed": expired_count,
                }
            }
        
        @app.get("/health")
        async def health():
            """Health check endpoint."""
            return {"status": "healthy"}


def create_inspection_app(proxy: LLMVPNProxy) -> FastAPI:
    """Create and configure FastAPI app for inspection API."""
    app = FastAPI(title="LLM-VPN Inspection API")
    api = InspectionAPI(proxy)
    api.setup_routes(app)
    return app
