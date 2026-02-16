"""
Chatbot Orchestrator v2
Simplified 3-step pipeline:
1. Unified Analyzer - Intent + Entities + Clarification check
2. Smart SQL + Validator - Generate and validate SQL
3. Response Formatter - Format results for user
"""
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from .database import db
from .conversation_manager import conversation_manager
from .agents.unified_analyzer import unified_analyzer
from .agents.smart_sql import smart_sql
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


class InvoiceChatbotV2:
    """
    Simplified chatbot with 3-step pipeline.
    Faster and more accurate than v1.
    """
    
    def __init__(self):
        self.db = db
    
    def chat(
        self, 
        question: str, 
        session_id: Optional[str] = None
    ) -> ChatResponse:
        """
        Process a user question and return a response.
        
        Pipeline:
        1. Unified Analyzer → Intent + Entities + Clarification
        2. Smart SQL → Generate SQL
        3. Response Formatter → Format results
        """
        try:
            # Get or create session
            session = conversation_manager.get_or_create_session(session_id)
            session_id = session.session_id
            
            # Add user message to history
            conversation_manager.add_message(session_id, "user", question)
            
            # Check if this is a response to a pending clarification
            if conversation_manager.has_pending_clarification(session_id):
                return self._handle_clarification_response(session_id, question)
            
            # Get conversation history
            history = conversation_manager.get_history_text(session_id)
            
            # ========== STEP 1: Unified Analysis ==========
            analysis = unified_analyzer.analyze(question, history)
            logger.info(f"Analysis: intent={analysis['intent']}, can_proceed={analysis['can_proceed']}")
            
            # Check if clarification is needed
            if not analysis["can_proceed"] and analysis.get("clarification"):
                clarification = analysis["clarification"]
                
                # Store pending clarification
                conversation_manager.set_pending_clarification(
                    session_id=session_id,
                    original_question=question,
                    clarifying_question=clarification["question"],
                    options=clarification["options"],
                    ambiguity_type="unified"
                )
                
                # Format clarification message
                options_text = "\n".join([f"  {i+1}. {opt}" for i, opt in enumerate(clarification["options"])])
                clarify_msg = f"{clarification['question']}\n\n{options_text}\n\n*Reply with your choice (1, 2, or 3)*"
                
                conversation_manager.add_message(session_id, "assistant", clarify_msg)
                
                return ChatResponse(
                    message=clarify_msg,
                    needs_clarification=True,
                    clarifying_question=clarification["question"],
                    options=clarification["options"],
                    session_id=session_id
                )
            
            # ========== STEP 2: Generate SQL ==========
            clarifications = conversation_manager.get_resolved_clarifications(session_id)
            clarifications_text = "None"
            if clarifications:
                clarifications_text = "\n".join([f"- {k}: {v}" for k, v in clarifications.items()])
            
            sql_result = smart_sql.generate_with_retry(
                question=question,
                intent=analysis["intent"],
                entities=analysis["entities"],
                tables=analysis["tables"],
                history=history,
                clarifications=clarifications_text
            )
            
            if not sql_result["success"]:
                error_msg = f"I couldn't generate a query for your question. Error: {sql_result['error']}"
                conversation_manager.add_message(session_id, "assistant", error_msg)
                return ChatResponse(
                    message=error_msg,
                    success=False,
                    error=sql_result["error"],
                    session_id=session_id
                )
            
            sql = sql_result["sql"]
            
            # ========== STEP 2.5: Rule-based Safety Validation ==========
            validation = sql_validator.validate(sql)
            
            if not validation["is_valid"]:
                issues = ", ".join(validation["issues"])
                error_msg = f"Query failed safety validation: {issues}"
                conversation_manager.add_message(session_id, "assistant", error_msg)
                return ChatResponse(
                    message=error_msg,
                    success=False,
                    error=issues,
                    sql_query=sql,
                    session_id=session_id
                )
            
            # ========== STEP 3: Execute Query ==========
            try:
                results, columns = self.db.execute_query(sql)
            except Exception as e:
                logger.warning(f"Query execution failed: {e}")
                
                # Try to regenerate with error feedback
                sql_result = smart_sql.generate(
                    question=question,
                    intent=analysis["intent"],
                    entities=analysis["entities"],
                    tables=analysis["tables"],
                    history=history,
                    clarifications=clarifications_text,
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
                            error_msg = f"Query failed: {str(e2)}"
                            conversation_manager.add_message(session_id, "assistant", error_msg)
                            return ChatResponse(
                                message=error_msg,
                                success=False,
                                error=str(e2),
                                sql_query=sql,
                                session_id=session_id
                            )
                    else:
                        error_msg = f"Query validation failed after retry"
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
            
            # ========== STEP 4: Format Response ==========
            formatted_response = response_formatter.format_response(
                question=question,
                sql=sql,
                results=results,
                columns=columns
            )
            
            # Store response in history
            conversation_manager.add_message(session_id, "assistant", formatted_response)
            
            return ChatResponse(
                message=formatted_response,
                sql_query=sql,
                data=results,
                session_id=session_id,
                success=True
            )
            
        except Exception as e:
            logger.error(f"Chat error: {e}", exc_info=True)
            error_msg = f"An error occurred: {str(e)}"
            return ChatResponse(
                message=error_msg,
                success=False,
                error=str(e),
                session_id=session_id
            )
    
    def _handle_clarification_response(
        self, 
        session_id: str, 
        user_response: str
    ) -> ChatResponse:
        """Handle user's response to a clarification question."""
        pending = conversation_manager.get_pending_clarification(session_id)
        
        if not pending:
            # No pending clarification, process as normal query
            history = conversation_manager.get_history_text(session_id)
            analysis = unified_analyzer.analyze(user_response, history)
            return self._process_with_analysis(session_id, user_response, analysis)
        
        # Parse the clarification response
        parse_result = unified_analyzer.parse_clarification_response(
            options=pending.options,
            user_response=user_response
        )
        
        if parse_result["parsed_successfully"]:
            # Store the resolved clarification
            conversation_manager.resolve_clarification(
                session_id, 
                parse_result["selected_option_text"]
            )
            
            # Process the original question with LLM analysis
            # Skip collision check since we already resolved the clarification
            history = conversation_manager.get_history_text(session_id)
            analysis = unified_analyzer.analyze(
                pending.original_question, 
                history,
                skip_collision_check=True  # Avoid re-triggering clarification
            )
            analysis["can_proceed"] = True  # Force proceed since we have clarification
            
            return self._process_with_analysis(session_id, pending.original_question, analysis)
        else:
            # Ask for clarification again
            options_text = "\n".join([f"  {i+1}. {opt}" for i, opt in enumerate(pending.options)])
            retry_msg = f"I didn't understand your choice. Please select:\n\n{options_text}\n\n*Reply with 1, 2, or 3*"
            
            return ChatResponse(
                message=retry_msg,
                needs_clarification=True,
                clarifying_question=pending.clarifying_question,
                options=pending.options,
                session_id=session_id
            )
    
    def _process_with_analysis(
        self,
        session_id: str,
        question: str,
        analysis: Dict[str, Any]
    ) -> ChatResponse:
        """Process a query with pre-computed analysis."""
        history = conversation_manager.get_history_text(session_id)
        clarifications = conversation_manager.get_resolved_clarifications(session_id)
        clarifications_text = "None"
        if clarifications:
            clarifications_text = "\n".join([f"- {k}: {v}" for k, v in clarifications.items()])
        
        # Generate SQL
        sql_result = smart_sql.generate_with_retry(
            question=question,
            intent=analysis["intent"],
            entities=analysis["entities"],
            tables=analysis["tables"],
            history=history,
            clarifications=clarifications_text
        )
        
        if not sql_result["success"]:
            error_msg = f"Query generation failed: {sql_result['error']}"
            conversation_manager.add_message(session_id, "assistant", error_msg)
            return ChatResponse(
                message=error_msg,
                success=False,
                error=sql_result["error"],
                session_id=session_id
            )
        
        sql = sql_result["sql"]
        
        # Validate
        validation = sql_validator.validate(sql)
        if not validation["is_valid"]:
            error_msg = f"Query validation failed: {validation['issues']}"
            conversation_manager.add_message(session_id, "assistant", error_msg)
            return ChatResponse(
                message=error_msg,
                success=False,
                error=str(validation['issues']),
                session_id=session_id
            )
        
        # Execute
        try:
            results, columns = self.db.execute_query(sql)
        except Exception as e:
            error_msg = f"Query execution failed: {str(e)}"
            conversation_manager.add_message(session_id, "assistant", error_msg)
            return ChatResponse(
                message=error_msg,
                success=False,
                error=str(e),
                sql_query=sql,
                session_id=session_id
            )
        
        # Format response
        formatted_response = response_formatter.format_response(
            question=question,
            sql=sql,
            results=results,
            columns=columns
        )
        
        conversation_manager.add_message(session_id, "assistant", formatted_response)
        
        return ChatResponse(
            message=formatted_response,
            sql_query=sql,
            data=results,
            session_id=session_id,
            success=True
        )


# Global chatbot instance (v2)
chatbot_v2 = InvoiceChatbotV2()
