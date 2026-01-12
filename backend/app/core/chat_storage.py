"""In-memory storage for chat sessions (bonus feature MVP)."""

from uuid import UUID
from typing import Optional, Dict

from app.core.schemas import ChatSession, ChatMessage


class InMemoryChatStore:
    """
    In-memory storage for chat sessions.
    
    For MVP/demo purposes only. Production should use a persistent store.
    """
    
    def __init__(self):
        """Initialize empty chat store."""
        self._sessions: Dict[UUID, ChatSession] = {}
    
    def create_session(self, job_id: UUID) -> UUID:
        """
        Create a new chat session for a job.
        
        Args:
            job_id: Job UUID to chat about
            
        Returns:
            Created session UUID
        """
        session = ChatSession(job_id=job_id)
        self._sessions[session.session_id] = session
        return session.session_id
    
    def get_session(self, session_id: UUID) -> Optional[ChatSession]:
        """
        Retrieve a chat session by ID.
        
        Args:
            session_id: Session UUID
            
        Returns:
            ChatSession if found, None otherwise
        """
        return self._sessions.get(session_id)
    
    def append_message(self, session_id: UUID, role: str, content: str) -> bool:
        """
        Append a message to a session.
        
        Args:
            session_id: Session UUID
            role: Message role ('user' or 'assistant')
            content: Message content
            
        Returns:
            True if message appended successfully, False if session not found
        """
        session = self._sessions.get(session_id)
        if not session:
            return False
        
        session.add_message(role=role, content=content)
        return True
    
    def delete_session(self, session_id: UUID) -> bool:
        """
        Delete a chat session.
        
        Args:
            session_id: Session UUID
            
        Returns:
            True if session deleted, False if not found
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False


# Global chat store instance
chat_store = InMemoryChatStore()
