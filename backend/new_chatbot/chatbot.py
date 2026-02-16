"""
Main chatbot orchestrator.
Coordinates all agents to process user questions.
"""
import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

from .database import db
from .conversation_manager import conversation_manager, ConversationSession
from .agents.ambiguity_detector import ambiguity_detector
from .agents.intent_classifier import intent_classifier
from .agents.sql_generator import sql_generator
from .agents.sql_validator import sql_validator
from .agents.response_formatter import response_formatter


logger = logging.getLogger(__name__)


@dataclass
class ChatResponse:
    """Represents a chatbot response."""
    message: str
    needs_clarification: bool = False
    clarifying_question: Optional[str] = None
    options: Optional[list] = None
    sql_query: Optional[str] = None
    data: Optional[list] = None
    session_id: Optional[str] = None
    success: bool = True
    error: Optional[str] = None


class InvoiceChatbot:
    """Main chatbot class that orchestrates all agents."""
    
    def __init__(self):
        self.db = db
    
    def chat(
        self, 
        question: str, 
        session_id: Optional[str] = None
    ) -> ChatResponse:
        """
        Process a user question and return a response.
        
        Args:
            question: The user's natural language question
            session_id: Optional session ID for context continuity
        
        Returns:
            ChatResponse with the answer or clarification request
        """
        try:
            # Get or create session
            session = conversation_manager.get_or_create_session(session_id)
            session_id = session.session_id
            
            # Expand incomplete queries using conversation history
            expanded_question = self._expand_query(session_id, question)
            if expanded_question != question:
                logger.info(f"Expanded query: '{question}' -> '{expanded_question}'")
                question = expanded_question
            
            # Add user message to history
            conversation_manager.add_message(session_id, "user", question)
            
            # Check if this is a response to a pending clarification
            if conversation_manager.has_pending_clarification(session_id):
                return self._handle_clarification_response(session_id, question)
            
            # Step 1: Check for ambiguity
            history = conversation_manager.get_history_text(session_id)
            ambiguity_result = ambiguity_detector.detect_ambiguity(question, history)
            
            if ambiguity_result["is_ambiguous"] and ambiguity_result["confidence"] > 0.7:
                # Store pending clarification
                conversation_manager.set_pending_clarification(
                    session_id=session_id,
                    original_question=question,
                    clarifying_question=ambiguity_result["clarifying_question"],
                    options=ambiguity_result["options"],
                    ambiguity_type=ambiguity_result["ambiguity_type"]
                )
                
                # Format clarification message
                options_text = "\n".join([f"  {i+1}. {opt}" for i, opt in enumerate(ambiguity_result["options"])])
                clarify_msg = f"{ambiguity_result['clarifying_question']}\n\n{options_text}\n\n*Please respond with your choice (1, 2, or 3).*"
                
                conversation_manager.add_message(session_id, "assistant", clarify_msg)
                
                return ChatResponse(
                    message=clarify_msg,
                    needs_clarification=True,
                    clarifying_question=ambiguity_result["clarifying_question"],
                    options=ambiguity_result["options"],
                    session_id=session_id
                )
            
            # Step 2: Proceed with query processing
            return self._process_query(session_id, question)
            
        except Exception as e:
            logger.error(f"Chat error: {e}", exc_info=True)
    
    def _expand_query(self, session_id: str, question: str) -> str:
        """
        Expand incomplete/follow-up queries using conversation history.
        
        Examples:
        - "and PO?" + previous "invoices from Google" -> "show PO from Google"
        - "what about pending?" + previous vendor context -> "show pending invoices from [vendor]"
        """
        import re
        
        # Check if query is too short or starts with connectors (likely follow-up)
        question_lower = question.lower().strip()
        followup_patterns = [
            r'^and\s+',       # "and PO?"
            r'^what\s+about\s+',  # "what about pending?"
            r'^also\s+',     # "also show..."
            r'^how\s+about\s+',  # "how about vendors?"
            r'^same\s+for\s+',   # "same for this month"
        ]
        
        is_followup = any(re.match(p, question_lower) for p in followup_patterns)
        is_short = len(question.split()) <= 3
        
        if not (is_followup or is_short):
            return question
        
        # Get last few messages to find context
        session = conversation_manager.get_session(session_id)
        if not session or len(session.history) < 2:
            return question
        
        # Find the last user query that had context (name, vendor, etc.)
        context_entity = None
        for msg in reversed(session.history[-6:]):  # Check last 6 messages
            if msg.role == "user":
                # Extract potential entity from previous message
                prev_text = msg.content.lower()
                
                # Look for "from X", "of X", "by X" patterns
                entity_patterns = [
                    r'from\s+(\w+)',
                    r'of\s+(\w+)',
                    r'by\s+(\w+)',
                    r'for\s+(\w+)',
                ]
                
                for pattern in entity_patterns:
                    match = re.search(pattern, prev_text)
                    if match:
                        entity = match.group(1)
                        # Skip common words
                        if entity not in ['the', 'this', 'that', 'last', 'all', 'my']:
                            context_entity = entity
                            break
                
                if context_entity:
                    break
        
        if not context_entity:
            return question
        
        # Expand the query with context
        # "and PO?" -> "show PO from [entity]"
        # "same for pending" -> "show pending from [entity]"
        
        # Remove the connector
        cleaned = re.sub(r'^(and|what\s+about|also|how\s+about|same\s+for)\s+', '', question_lower).strip()
        cleaned = cleaned.rstrip('?')
        
        # Build expanded query
        expanded = f"show {cleaned} from {context_entity}"

        return expanded
    
    def _handle_clarification_response(
        self, 
        session_id: str, 
        user_response: str
    ) -> ChatResponse:
        """Handle user's response to a clarification question."""
        pending = conversation_manager.get_pending_clarification(session_id)
        
        if not pending:
            return self._process_query(session_id, user_response)
        
        # Parse the clarification response
        parse_result = ambiguity_detector.parse_clarification_response(
            original_question=pending.original_question,
            clarifying_question=pending.clarifying_question,
            options=pending.options,
            user_response=user_response
        )
        
        if parse_result["parsed_successfully"]:
            # Store the resolved clarification
            conversation_manager.resolve_clarification(
                session_id, 
                parse_result["selected_option_text"]
            )
            
            # Now process the original question with clarification context
            return self._process_query(session_id, pending.original_question)
        else:
            # Ask for clarification again
            options_text = "\n".join([f"  {i+1}. {opt}" for i, opt in enumerate(pending.options)])
            retry_msg = f"I didn't understand your choice. Please select from these options:\n\n{options_text}\n\n*Please respond with 1, 2, or 3.*"
            
            return ChatResponse(
                message=retry_msg,
                needs_clarification=True,
                clarifying_question=pending.clarifying_question,
                options=pending.options,
                session_id=session_id
            )
    
    def _process_query(self, session_id: str, question: str) -> ChatResponse:
        """Process a query through the full pipeline."""
        
        # Get context
        context = conversation_manager.get_context_for_prompt(session_id)
        clarifications = conversation_manager.get_resolved_clarifications(session_id)
        history = conversation_manager.get_history_text(session_id)
        
        # Step 1: Classify intent
        intent = intent_classifier.classify(question, context)
        logger.info(f"Intent: {intent['primary_intent']}, Tables: {intent['tables_involved']}")
        
        # Step 2: Generate SQL
        sql_result = sql_generator.generate_with_retry(
            question=question,
            intent=intent,
            clarifications=clarifications,
            history=history
        )
        
        if not sql_result["success"]:
            error_msg = f"I couldn't generate a valid query for your question. Error: {sql_result['error']}"
            conversation_manager.add_message(session_id, "assistant", error_msg)
            return ChatResponse(
                message=error_msg,
                success=False,
                error=sql_result["error"],
                session_id=session_id
            )
        
        sql = sql_result["sql"]
        
        # Step 3: Validate SQL
        validation = sql_validator.validate(sql)
        
        if not validation["is_valid"]:
            issues = ", ".join(validation["issues"])
            error_msg = f"The generated query failed safety validation: {issues}"
            conversation_manager.add_message(session_id, "assistant", error_msg)
            return ChatResponse(
                message=error_msg,
                success=False,
                error=issues,
                sql_query=sql,
                session_id=session_id
            )
        
        # Step 4: Execute query
        try:
            results, columns = self.db.execute_query(sql)
        except Exception as e:
            # Try to regenerate SQL with error feedback
            logger.warning(f"Query execution failed: {e}")
            
            sql_result = sql_generator.generate(
                question=question,
                intent=intent,
                clarifications=clarifications,
                history=history,
                retry_count=1,
                previous_error=str(e)
            )
            
            if sql_result["success"]:
                sql = sql_result["sql"]
                validation = sql_validator.validate(sql)
                if validation["is_valid"]:
                    try:
                        results, columns = self.db.execute_query(sql)
                    except Exception as e2:
                        error_msg = f"Query execution failed: {str(e2)}"
                        conversation_manager.add_message(session_id, "assistant", error_msg)
                        return ChatResponse(
                            message=error_msg,
                            success=False,
                            error=str(e2),
                            sql_query=sql,
                            session_id=session_id
                        )
                else:
                    error_msg = f"Query validation failed: {validation['issues']}"
                    conversation_manager.add_message(session_id, "assistant", error_msg)
                    return ChatResponse(
                        message=error_msg,
                        success=False,
                        error=str(validation['issues']),
                        session_id=session_id
                    )
            else:
                error_msg = f"Unable to execute query: {str(e)}"
                conversation_manager.add_message(session_id, "assistant", error_msg)
                return ChatResponse(
                    message=error_msg,
                    success=False,
                    error=str(e),
                    session_id=session_id
                )
        
        # Step 5: Format response
        formatted_response = response_formatter.format_response(
            question=question,
            sql=sql,
            results=results,
            columns=columns
        )
        
        # Log SQL to terminal only (not shown to user)
        logger.info(f"📝 SQL Query: {sql}")
        
        # Store response in history
        conversation_manager.add_message(session_id, "assistant", formatted_response)
        
        return ChatResponse(
            message=formatted_response,  # Clean response without SQL
            sql_query=sql,  # Still available in response object for debugging
            data=results,
            session_id=session_id,
            success=True
        )


# Global chatbot instance
chatbot = InvoiceChatbot()
