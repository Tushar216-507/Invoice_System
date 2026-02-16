"""
Conversation context manager for multi-turn dialogues.
Handles session state, clarification flows, and conversation history.
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import uuid
import json


@dataclass
class Message:
    """Represents a single message in conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)


@dataclass
class ClarificationState:
    """Tracks pending clarification."""
    original_question: str
    clarifying_question: str
    options: List[str]
    ambiguity_type: str
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ConversationSession:
    """Represents a conversation session."""
    session_id: str
    history: List[Message] = field(default_factory=list)
    pending_clarification: Optional[ClarificationState] = None
    resolved_clarifications: Dict[str, str] = field(default_factory=dict)
    context: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)


class ConversationManager:
    """Manages conversation sessions and context."""
    
    def __init__(self):
        self._sessions: Dict[str, ConversationSession] = {}
    
    def create_session(self) -> str:
        """Create a new conversation session."""
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = ConversationSession(session_id=session_id)
        return session_id
    
    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """Get session by ID, returns None if not found."""
        return self._sessions.get(session_id)
    
    def get_or_create_session(self, session_id: Optional[str] = None) -> ConversationSession:
        """Get existing session or create new one."""
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        
        new_id = session_id or str(uuid.uuid4())
        session = ConversationSession(session_id=new_id)
        self._sessions[new_id] = session
        return session
    
    def add_message(self, session_id: str, role: str, content: str, metadata: Dict = None):
        """Add a message to conversation history."""
        session = self.get_session(session_id)
        if session:
            message = Message(
                role=role,
                content=content,
                metadata=metadata or {}
            )
            session.history.append(message)
            session.last_activity = datetime.now()
    
    def get_history_text(self, session_id: str, max_messages: int = 10) -> str:
        """Get conversation history as formatted text."""
        session = self.get_session(session_id)
        if not session or not session.history:
            return "No previous conversation."
        
        recent = session.history[-max_messages:]
        lines = []
        for msg in recent:
            role_label = "User" if msg.role == "user" else "Assistant"
            lines.append(f"{role_label}: {msg.content}")
        
        return "\n".join(lines)
    
    def set_pending_clarification(
        self, 
        session_id: str, 
        original_question: str,
        clarifying_question: str,
        options: List[str],
        ambiguity_type: str
    ):
        """Set a pending clarification request."""
        session = self.get_session(session_id)
        if session:
            session.pending_clarification = ClarificationState(
                original_question=original_question,
                clarifying_question=clarifying_question,
                options=options,
                ambiguity_type=ambiguity_type
            )
    
    def has_pending_clarification(self, session_id: str) -> bool:
        """Check if session has pending clarification."""
        session = self.get_session(session_id)
        return session is not None and session.pending_clarification is not None
    
    def get_pending_clarification(self, session_id: str) -> Optional[ClarificationState]:
        """Get pending clarification state."""
        session = self.get_session(session_id)
        return session.pending_clarification if session else None
    
    def resolve_clarification(self, session_id: str, selected_option: str):
        """Resolve a pending clarification with user's choice."""
        session = self.get_session(session_id)
        if session and session.pending_clarification:
            # Store the resolved clarification
            key = session.pending_clarification.ambiguity_type
            session.resolved_clarifications[key] = selected_option
            session.pending_clarification = None
    
    def get_resolved_clarifications(self, session_id: str) -> Dict[str, str]:
        """Get all resolved clarifications for a session."""
        session = self.get_session(session_id)
        return session.resolved_clarifications if session else {}
    
    def clear_session(self, session_id: str):
        """Clear all session data."""
        if session_id in self._sessions:
            del self._sessions[session_id]
    
    def get_context_for_prompt(self, session_id: str) -> str:
        """Get formatted context for LLM prompts."""
        session = self.get_session(session_id)
        if not session:
            return ""
        
        context_parts = []
        
        # Add resolved clarifications
        if session.resolved_clarifications:
            context_parts.append("Previously clarified:")
            for key, value in session.resolved_clarifications.items():
                context_parts.append(f"  - {key}: {value}")
        
        # Add any stored context
        if session.context:
            context_parts.append(f"Context: {json.dumps(session.context)}")
        
        return "\n".join(context_parts)


# Global conversation manager
conversation_manager = ConversationManager()
