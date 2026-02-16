"""
backend/state_manager.py - Conversation State Management
Handles multi-step confirmation flows for chatbot queries
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    """Possible states in the conversation flow"""
    INITIAL = "initial"
    AWAITING_ENTITY_SELECTION = "awaiting_entity_selection"
    AWAITING_DATE_RANGE = "awaiting_date_range"
    READY_TO_QUERY = "ready_to_query"
    COMPLETED = "completed"


class StateManager:
    """
    Manages conversation state for multi-step query clarification
    """

    def __init__(self):
        """Initialize state manager"""
        self.conversations: Dict[str, Dict] = {}
        logger.info("✅ StateManager initialized")

    # ====================================================================
    # CONVERSATION LIFECYCLE
    # ====================================================================

    def create_conversation(self) -> str:
        """
        Create new conversation with initial state
        
        Returns:
            Conversation ID
        """
        conv_id = str(uuid.uuid4())
        self.conversations[conv_id] = {
            "id": conv_id,
            "created_at": datetime.now().isoformat(),
            "state": ConversationState.INITIAL.value,
            "original_message": None,
            "search_results": None,
            "selected_entity": None,
            "date_range": None,
            "generated_sql": None,
            "history": [],
            "metadata": {}
        }
        logger.info(f"📌 Created conversation: {conv_id}")
        return conv_id

    def get_conversation(self, conv_id: str) -> Optional[Dict]:
        """
        Get conversation by ID
        
        Args:
            conv_id: Conversation ID
            
        Returns:
            Conversation dictionary or None
        """
        return self.conversations.get(conv_id)

    def delete_conversation(self, conv_id: str) -> bool:
        """
        Delete conversation
        
        Args:
            conv_id: Conversation ID
            
        Returns:
            True if deleted, False if not found
        """
        if conv_id in self.conversations:
            del self.conversations[conv_id]
            logger.info(f"🗑️ Deleted conversation: {conv_id}")
            return True
        return False

    # ====================================================================
    # STATE TRANSITIONS
    # ====================================================================

    def set_state(self, conv_id: str, state: ConversationState) -> bool:
        """
        Update conversation state
        
        Args:
            conv_id: Conversation ID
            state: New state
            
        Returns:
            True if updated, False if conversation not found
        """
        if conv_id in self.conversations:
            old_state = self.conversations[conv_id]["state"]
            self.conversations[conv_id]["state"] = state.value
            logger.info(f"🔄 Conversation {conv_id}: {old_state} → {state.value}")
            return True
        return False

    def get_state(self, conv_id: str) -> Optional[str]:
        """
        Get current conversation state
        
        Args:
            conv_id: Conversation ID
            
        Returns:
            State string or None
        """
        conv = self.get_conversation(conv_id)
        return conv["state"] if conv else None

    # ====================================================================
    # DATA STORAGE
    # ====================================================================

    def store_original_message(self, conv_id: str, message: str) -> bool:
        """
        Store the original user message
        
        Args:
            conv_id: Conversation ID
            message: User's original message
            
        Returns:
            True if stored, False if conversation not found
        """
        if conv_id in self.conversations:
            self.conversations[conv_id]["original_message"] = message
            logger.info(f"💬 Stored original message for {conv_id}")
            return True
        return False

    def store_search_results(self, conv_id: str, results: Dict) -> bool:
        """
        Store entity search results
        
        Args:
            conv_id: Conversation ID
            results: Search results from disambiguation engine
            
        Returns:
            True if stored, False if conversation not found
        """
        if conv_id in self.conversations:
            self.conversations[conv_id]["search_results"] = results
            self.conversations[conv_id]["state"] = ConversationState.AWAITING_ENTITY_SELECTION.value
            logger.info(f"🔍 Stored search results for {conv_id}")
            return True
        return False

    def store_selected_entity(self, conv_id: str, entity: Dict) -> bool:
        """
        Store user's selected entity
        
        Args:
            conv_id: Conversation ID
            entity: Selected entity dictionary
            
        Returns:
            True if stored, False if conversation not found
        """
        if conv_id in self.conversations:
            self.conversations[conv_id]["selected_entity"] = entity
            
            # If vendor, need date range next
            if entity.get("type") == "vendor":
                self.conversations[conv_id]["state"] = ConversationState.AWAITING_DATE_RANGE.value
                logger.info(f"📅 Entity selected, awaiting date range for {conv_id}")
            else:
                # User queries don't need date range
                self.conversations[conv_id]["state"] = ConversationState.READY_TO_QUERY.value
                logger.info(f"✅ Entity selected, ready to query for {conv_id}")
            
            return True
        return False

    def store_date_range(self, conv_id: str, from_date: str, to_date: str) -> bool:
        """
        Store user's selected date range
        
        Args:
            conv_id: Conversation ID
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            
        Returns:
            True if stored, False if conversation not found
        """
        if conv_id in self.conversations:
            self.conversations[conv_id]["date_range"] = {
                "from": from_date,
                "to": to_date
            }
            self.conversations[conv_id]["state"] = ConversationState.READY_TO_QUERY.value
            logger.info(f"📅 Date range stored, ready to query for {conv_id}")
            return True
        return False

    def store_generated_sql(self, conv_id: str, sql: str) -> bool:
        """
        Store generated SQL query
        
        Args:
            conv_id: Conversation ID
            sql: Generated SQL query
            
        Returns:
            True if stored, False if conversation not found
        """
        if conv_id in self.conversations:
            self.conversations[conv_id]["generated_sql"] = sql
            logger.info(f"💾 Stored generated SQL for {conv_id}")
            return True
        return False

    # ====================================================================
    # HISTORY MANAGEMENT
    # ====================================================================

    def add_to_history(self, conv_id: str, entry: Dict) -> bool:
        """
        Add entry to conversation history
        
        Args:
            conv_id: Conversation ID
            entry: History entry dictionary
            
        Returns:
            True if added, False if conversation not found
        """
        if conv_id in self.conversations:
            entry["timestamp"] = datetime.now().isoformat()
            self.conversations[conv_id]["history"].append(entry)
            logger.info(f"📝 Added history entry to {conv_id}")
            return True
        return False

    def get_history(self, conv_id: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Get conversation history
        
        Args:
            conv_id: Conversation ID
            limit: Maximum number of entries to return (most recent)
            
        Returns:
            List of history entries
        """
        conv = self.get_conversation(conv_id)
        if not conv:
            return []
        
        history = conv["history"]
        if limit:
            return history[-limit:]
        return history

    # ====================================================================
    # VALIDATION & CHECKS
    # ====================================================================

    def is_ready_to_query(self, conv_id: str) -> bool:
        """
        Check if conversation has all required data to execute query
        
        Args:
            conv_id: Conversation ID
            
        Returns:
            True if ready, False otherwise
        """
        conv = self.get_conversation(conv_id)
        if not conv:
            return False
        
        # Must have selected entity
        if not conv.get("selected_entity"):
            return False
        
        entity = conv["selected_entity"]
        
        # Vendor queries MUST have date range
        if entity.get("type") == "vendor" and not conv.get("date_range"):
            return False
        
        # User queries don't need date range
        return True

    def needs_entity_selection(self, conv_id: str) -> bool:
        """
        Check if conversation is awaiting entity selection
        
        Args:
            conv_id: Conversation ID
            
        Returns:
            True if awaiting selection, False otherwise
        """
        state = self.get_state(conv_id)
        return state == ConversationState.AWAITING_ENTITY_SELECTION.value

    def needs_date_range(self, conv_id: str) -> bool:
        """
        Check if conversation is awaiting date range
        
        Args:
            conv_id: Conversation ID
            
        Returns:
            True if awaiting date range, False otherwise
        """
        state = self.get_state(conv_id)
        return state == ConversationState.AWAITING_DATE_RANGE.value

    # ====================================================================
    # METADATA
    # ====================================================================

    def set_metadata(self, conv_id: str, key: str, value: any) -> bool:
        """
        Store metadata for conversation
        
        Args:
            conv_id: Conversation ID
            key: Metadata key
            value: Metadata value
            
        Returns:
            True if stored, False if conversation not found
        """
        if conv_id in self.conversations:
            self.conversations[conv_id]["metadata"][key] = value
            return True
        return False

    def get_metadata(self, conv_id: str, key: str) -> Optional[any]:
        """
        Get metadata value
        
        Args:
            conv_id: Conversation ID
            key: Metadata key
            
        Returns:
            Metadata value or None
        """
        conv = self.get_conversation(conv_id)
        if conv:
            return conv["metadata"].get(key)
        return None

    # ====================================================================
    # CLEANUP
    # ====================================================================

    def cleanup_old_conversations(self, max_age_hours: int = 2) -> int:
        """
        Remove conversations older than max_age_hours
        
        Args:
            max_age_hours: Maximum age in hours
            
        Returns:
            Number of conversations deleted
        """
        from datetime import datetime, timedelta
        
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        to_remove = []
        
        for conv_id, conv in self.conversations.items():
            try:
                created = datetime.fromisoformat(conv["created_at"])
                if created < cutoff:
                    to_remove.append(conv_id)
            except (ValueError, TypeError, KeyError):
                # Invalid timestamp, remove it
                to_remove.append(conv_id)
        
        for conv_id in to_remove:
            del self.conversations[conv_id]
        
        if to_remove:
            logger.info(f"🗑️ Cleaned up {len(to_remove)} old conversations")
        
        return len(to_remove)

    def get_conversation_count(self) -> int:
        """
        Get total number of active conversations
        
        Returns:
            Count of conversations
        """
        return len(self.conversations)


# ============================================================================
# GLOBAL INSTANCE (will be created in agent_v2.py)
# ============================================================================
