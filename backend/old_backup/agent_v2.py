"""
backend/agent_v2.py - New Chatbot Agent with Disambiguation
Zero-hallucination architecture with mandatory user confirmations
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime
import json

# Import existing components (keep these!)
from backend.ai_clients import sql_generator, response_formatter, qwen_client
from backend.db import db_instance

# Import new components
from backend.disambiguation_engine import DisambiguationEngine
from backend.state_manager import StateManager, ConversationState
from backend.api_schemas import ResponseBuilder, DateRangeHelper

logger = logging.getLogger(__name__)


class ChatBotV2:
    """
    New chatbot with zero-hallucination architecture
    
    Key Features:
    - Disambiguates users vs vendors before query
    - Requires explicit date range for vendor queries
    - No LLM guessing - all parameters confirmed by user
    - Keeps LLM for SQL generation (dynamic, flexible)
    """

    def __init__(self):
        """Initialize chatbot with new components"""
        self.state_manager = StateManager()
        self.disambiguator = DisambiguationEngine(db_instance)
        
        logger.info("=" * 70)
        logger.info("✅ ChatBotV2 Initialized")
        logger.info("  - Disambiguation Engine: Ready")
        logger.info("  - State Manager: Ready")
        logger.info("  - SQL Generator (LLM): Ready")
        logger.info("  - Response Formatter (LLM): Ready")
        logger.info("=" * 70)

    # ====================================================================
    # MAIN ENTRY POINT
    # ====================================================================

    async def process_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        confirmation_data: Optional[Dict] = None
    ) -> Dict:
        """
        Process user message or confirmation
        
        Args:
            message: User's message (for new queries)
            conversation_id: Existing conversation ID (optional)
            confirmation_data: Confirmation data from user (entity selection, date range)
            
        Returns:
            Response dictionary
        """
        try:
            logger.info("=" * 70)
            logger.info("📨 NEW REQUEST")
            logger.info(f"Message: {message[:100] if message else 'None'}")
            logger.info(f"Conversation ID: {conversation_id or 'New'}")
            logger.info(f"Has Confirmation: {bool(confirmation_data)}")
            logger.info("=" * 70)

            # Cleanup old conversations periodically
            if self.state_manager.get_conversation_count() > 50:
                self.state_manager.cleanup_old_conversations(max_age_hours=2)

            # Create new conversation if needed
            if not conversation_id:
                conversation_id = self.state_manager.create_conversation()

            # Route based on whether this is a confirmation or new message
            if confirmation_data:
                return await self._handle_confirmation(conversation_id, confirmation_data)
            else:
                return await self._handle_new_message(conversation_id, message)

        except Exception as e:
            logger.error(f"❌ Fatal error in process_message: {str(e)}", exc_info=True)
            return ResponseBuilder.error_response(
                conversation_id=conversation_id or "unknown",
                error_message=f"System error: {str(e)}",
                error_type="system_error"
            )

    # ====================================================================
    # NEW MESSAGE HANDLER
    # ====================================================================

    async def _handle_new_message(self, conversation_id: str, message: str) -> Dict:
        """
        Handle new user message (not a confirmation)
        
        Args:
            conversation_id: Conversation ID
            message: User's message
            
        Returns:
            Response dictionary
        """
        try:
            logger.info("🆕 Processing NEW MESSAGE")
            
            # Store original message
            self.state_manager.store_original_message(conversation_id, message)

            # ================================================================
            # STEP 1: DISAMBIGUATION - Search for entities
            # ================================================================
            logger.info("=" * 70)
            logger.info("🔍 STEP 1: DISAMBIGUATION")
            logger.info("=" * 70)

            search_results = self.disambiguator.search_all_entities(message)
            
            logger.info(f"Search Results:")
            logger.info(f"  - Vendors: {len(search_results['vendor_matches'])}")
            logger.info(f"  - Users: {len(search_results['user_matches'])}")
            logger.info(f"  - Total: {search_results['total_matches']}")

            # Store search results in conversation state
            self.state_manager.store_search_results(conversation_id, search_results)

            # ================================================================
            # CASE 1: No matches found
            # ================================================================
            if search_results['total_matches'] == 0:
                logger.warning("⚠️ No entities found matching search terms")
                return ResponseBuilder.no_matches_found(
                    conversation_id=conversation_id,
                    search_terms=search_results['search_terms']
                )

            # ================================================================
            # CASE 2: Multiple matches - need clarification
            # ================================================================
            if search_results['total_matches'] > 1:
                logger.info("🤔 Multiple matches found - requesting user selection")
                return ResponseBuilder.needs_entity_clarification(
                    conversation_id=conversation_id,
                    message=None,  # Use default message
                    vendor_matches=search_results['vendor_matches'],
                    user_matches=search_results['user_matches'],
                    search_terms=search_results['search_terms']
                )

            # ================================================================
            # CASE 3: Single match - auto-select
            # ================================================================
            logger.info("✅ Single match found - auto-selecting")
            
            if search_results['vendor_matches']:
                selected_entity = search_results['vendor_matches'][0]
            else:
                selected_entity = search_results['user_matches'][0]

            # Store selected entity
            self.state_manager.store_selected_entity(conversation_id, selected_entity)

            # ================================================================
            # CASE 3a: Vendor - need date range
            # ================================================================
            if selected_entity['type'] == 'vendor':
                logger.info("📅 Vendor selected - requesting date range")
                return ResponseBuilder.needs_date_range(
                    conversation_id=conversation_id,
                    selected_entity=selected_entity
                )

            # ================================================================
            # CASE 3b: User - ready to query (no date range needed)
            # ================================================================
            logger.info("✅ User selected - ready to query")
            return await self._execute_query(conversation_id)

        except Exception as e:
            logger.error(f"❌ Error in _handle_new_message: {str(e)}", exc_info=True)
            return ResponseBuilder.error_response(
                conversation_id=conversation_id,
                error_message=f"Error processing message: {str(e)}",
                error_type="processing_error"
            )

    # ====================================================================
    # CONFIRMATION HANDLER
    # ====================================================================

    async def _handle_confirmation(self, conversation_id: str, confirmation_data: Dict) -> Dict:
        """
        Handle user confirmation (entity selection or date range)
        
        Args:
            conversation_id: Conversation ID
            confirmation_data: {
                "type": "entity_selection" | "date_range",
                "entity_id": int,
                "entity_type": "vendor" | "user",
                "date_range": {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"} | "quick_pick_value"
            }
            
        Returns:
            Response dictionary
        """
        try:
            logger.info("✅ Processing CONFIRMATION")
            logger.info(f"Confirmation Type: {confirmation_data.get('type')}")

            confirmation_type = confirmation_data.get("type")

            # ================================================================
            # CONFIRMATION TYPE 1: Entity Selection
            # ================================================================
            if confirmation_type == "entity_selection":
                entity_id = confirmation_data.get("entity_id")
                entity_type = confirmation_data.get("entity_type")

                if not entity_id or not entity_type:
                    return ResponseBuilder.error_response(
                        conversation_id=conversation_id,
                        error_message="Invalid entity selection. Please try again.",
                        error_type="validation_error"
                    )

                # Get full entity details
                entity = self.disambiguator.get_entity_by_id(entity_type, entity_id)
                
                if not entity:
                    return ResponseBuilder.error_response(
                        conversation_id=conversation_id,
                        error_message="Selected entity not found. Please try again.",
                        error_type="not_found"
                    )

                logger.info(f"📌 Entity Confirmed: {entity['name']} ({entity['type']})")
                
                # Store selected entity
                self.state_manager.store_selected_entity(conversation_id, entity)

                # If vendor, need date range
                if entity['type'] == 'vendor':
                    logger.info("📅 Vendor confirmed - requesting date range")
                    return ResponseBuilder.needs_date_range(
                        conversation_id=conversation_id,
                        selected_entity=entity
                    )
                
                # If user, ready to query
                logger.info("✅ User confirmed - ready to query")
                return await self._execute_query(conversation_id)

            # ================================================================
            # CONFIRMATION TYPE 2: Date Range
            # ================================================================
            elif confirmation_type == "date_range":
                date_range_input = confirmation_data.get("date_range")

                if not date_range_input:
                    return ResponseBuilder.error_response(
                        conversation_id=conversation_id,
                        error_message="No date range provided. Please try again.",
                        error_type="validation_error"
                    )

                # Handle quick pick values
                if isinstance(date_range_input, str):
                    date_range = DateRangeHelper.get_date_range(date_range_input)
                    if not date_range:
                        return ResponseBuilder.error_response(
                            conversation_id=conversation_id,
                            error_message=f"Invalid quick pick value: {date_range_input}",
                            error_type="validation_error"
                        )
                else:
                    # Custom date range
                    date_range = date_range_input

                # Validate date range
                is_valid, error_msg = DateRangeHelper.validate_date_range(
                    date_range['from'],
                    date_range['to']
                )

                if not is_valid:
                    return ResponseBuilder.error_response(
                        conversation_id=conversation_id,
                        error_message=error_msg,
                        error_type="validation_error"
                    )

                logger.info(f"📅 Date Range Confirmed: {date_range['from']} to {date_range['to']}")
                
                # Store date range
                self.state_manager.store_date_range(
                    conversation_id,
                    date_range['from'],
                    date_range['to']
                )

                # Ready to query
                logger.info("✅ All parameters confirmed - ready to query")
                return await self._execute_query(conversation_id)

            else:
                return ResponseBuilder.error_response(
                    conversation_id=conversation_id,
                    error_message=f"Unknown confirmation type: {confirmation_type}",
                    error_type="validation_error"
                )

        except Exception as e:
            logger.error(f"❌ Error in _handle_confirmation: {str(e)}", exc_info=True)
            return ResponseBuilder.error_response(
                conversation_id=conversation_id,
                error_message=f"Error processing confirmation: {str(e)}",
                error_type="processing_error"
            )

    # ====================================================================
    # QUERY EXECUTION (with LLM)
    # ====================================================================

    async def _execute_query(self, conversation_id: str) -> Dict:
        """
        Execute query with confirmed parameters
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Response dictionary
        """
        try:
            # Verify we're ready to query
            if not self.state_manager.is_ready_to_query(conversation_id):
                return ResponseBuilder.error_response(
                    conversation_id=conversation_id,
                    error_message="Missing required parameters. Please start over.",
                    error_type="invalid_state"
                )

            logger.info("=" * 70)
            logger.info("🚀 EXECUTING QUERY")
            logger.info("=" * 70)

            # Get conversation data
            conv = self.state_manager.get_conversation(conversation_id)
            original_message = conv['original_message']
            selected_entity = conv['selected_entity']
            date_range = conv.get('date_range')

            logger.info(f"Original Message: {original_message}")
            logger.info(f"Entity: {selected_entity['name']} ({selected_entity['type']})")
            if date_range:
                logger.info(f"Date Range: {date_range['from']} to {date_range['to']}")

            # ================================================================
            # STEP 2: SQL GENERATION (with LLM - but NO guessing!)
            # ================================================================
            logger.info("=" * 70)
            logger.info("🤖 STEP 2: SQL GENERATION (LLM)")
            logger.info("=" * 70)

            sql = await self._generate_sql_with_confirmed_params(
                original_message=original_message,
                entity=selected_entity,
                date_range=date_range
            )

            logger.info(f"Generated SQL: {sql[:300]}...")
            
            # Store SQL
            self.state_manager.store_generated_sql(conversation_id, sql)

            # ================================================================
            # STEP 3: EXECUTE SQL
            # ================================================================
            logger.info("=" * 70)
            logger.info("💾 STEP 3: EXECUTE QUERY")
            logger.info("=" * 70)

            results = db_instance.execute_query(sql)
            
            logger.info(f"✅ Query returned {len(results)} rows")

            # ================================================================
            # STEP 4: FORMAT RESPONSE (with LLM)
            # ================================================================
            logger.info("=" * 70)
            logger.info("✨ STEP 4: FORMAT RESPONSE (LLM)")
            logger.info("=" * 70)

            response_text = await self._format_response(
                data=results,
                original_message=original_message,
                entity=selected_entity,
                date_range=date_range
            )

            logger.info(f"Formatted Response: {response_text[:200]}...")

            # ================================================================
            # Update conversation history
            # ================================================================
            self.state_manager.add_to_history(conversation_id, {
                "type": "query_execution",
                "original_message": original_message,
                "selected_entity": selected_entity,
                "date_range": date_range,
                "sql": sql,
                "result_count": len(results),
                "response": response_text
            })

            # Mark as completed
            self.state_manager.set_state(conversation_id, ConversationState.COMPLETED)

            logger.info("=" * 70)
            logger.info("✅ QUERY EXECUTION COMPLETE")
            logger.info("=" * 70)

            # ================================================================
            # Return success response
            # ================================================================
            return ResponseBuilder.query_success(
                conversation_id=conversation_id,
                response_text=response_text,
                data=results,
                sql=sql,
                selected_entity=selected_entity,
                date_range=date_range
            )

        except Exception as e:
            logger.error(f"❌ Error in _execute_query: {str(e)}", exc_info=True)
            return ResponseBuilder.error_response(
                conversation_id=conversation_id,
                error_message=f"Query execution failed: {str(e)}",
                error_type="execution_error"
            )

    # ====================================================================
    # SQL GENERATION (LLM with CONFIRMED parameters)
    # ====================================================================

    async def _generate_sql_with_confirmed_params(
        self,
        original_message: str,
        entity: Dict,
        date_range: Optional[Dict]
    ) -> str:
        """
        Generate SQL using LLM with confirmed parameters
        
        Args:
            original_message: User's original question
            entity: Confirmed entity (vendor or user)
            date_range: Confirmed date range (if applicable)
            
        Returns:
            SQL query string
        """
        try:
            # Get database schema
            schema = db_instance.get_schema()

            # Build enhanced prompt with CONFIRMED parameters
            prompt = f"""
You are a SQL query generator for an invoice management system.

USER'S ORIGINAL QUESTION:
{original_message}

CONFIRMED PARAMETERS (DO NOT GUESS OR CHANGE THESE):

Entity Type: {entity['type'].upper()}
Entity ID: {entity['id']}
Entity Name: {entity['name']}
"""

            if entity['type'] == 'vendor':
                prompt += f"""
Shortform: {entity.get('shortform', 'N/A')}

CRITICAL: Use vendor name EXACTLY as: "{entity['name']}"
Match invoices WHERE invoices.vendor = "{entity['name']}"
"""

            if entity['type'] == 'user':
                prompt += f"""
Email: {entity.get('email', 'N/A')}
Role: {entity.get('role', 'N/A')}

CRITICAL: Use user name EXACTLY as: "{entity['name']}"
Match invoices WHERE created_by = "{entity['name']}" OR approved_by = "{entity['name']}" OR reviewed_by = "{entity['name']}"
"""

            if date_range:
                prompt += f"""
CONFIRMED DATE RANGE (DO NOT CHANGE):
From: {date_range['from']}
To: {date_range['to']}

CRITICAL: Use EXACT date filter:
WHERE invoice_date >= '{date_range['from']}' AND invoice_date <= '{date_range['to']}'
"""

            prompt += f"""

DATABASE SCHEMA:
{schema}

CRITICAL RULES:
1. Use the EXACT entity name provided: "{entity['name']}"
2. Use the EXACT entity ID: {entity['id']}
3. {f"Use the EXACT date range: {date_range['from']} to {date_range['to']}" if date_range else "NO DATE FILTER (user did not provide one)"}
4. DO NOT add any other filters or assumptions
5. DO NOT guess or infer anything
6. User has explicitly confirmed these parameters
7. Return ONLY the SQL query, no explanations

Generate the SQL query now:
"""

            # Call SQL generator LLM
            sql = await sql_generator.generate(
                message=original_message,
                intent="query",  # Generic intent
                schema=schema,
                conversation_history=[],
                vendor_list=[entity] if entity['type'] == 'vendor' else [],
                user_list=[entity] if entity['type'] == 'user' else [],
                confirmed_entity=entity,  # NEW: Pass confirmed entity
                confirmed_date_range=date_range  # NEW: Pass confirmed date range
            )

            return sql.strip()

        except Exception as e:
            logger.error(f"❌ SQL generation failed: {str(e)}")
            raise Exception(f"Failed to generate SQL: {str(e)}")

    # ====================================================================
    # RESPONSE FORMATTING (LLM)
    # ====================================================================

    async def _format_response(
        self,
        data: List[Dict],
        original_message: str,
        entity: Dict,
        date_range: Optional[Dict]
    ) -> str:
        """
        Format query results into natural language response
        
        Args:
            data: Query results
            original_message: User's original question
            entity: Selected entity
            date_range: Date range used (if applicable)
            
        Returns:
            Formatted response text
        """
        try:
            # Use existing response formatter
            response = await response_formatter.format(
                data=data,
                intent="query",
                message=original_message
            )

            return response

        except Exception as e:
            logger.error(f"❌ Response formatting failed: {str(e)}")
            # Fallback to simple response
            if len(data) == 0:
                return f"No records found for {entity['name']}."
            else:
                return f"Found {len(data)} records for {entity['name']}. Please see the data table below."


# ============================================================================
# CREATE GLOBAL INSTANCE
# ============================================================================

try:
    chatbot_v2_instance = ChatBotV2()
    logger.info("✅ ChatBotV2 instance created successfully")
except Exception as e:
    logger.error(f"❌ ChatBotV2 initialization failed: {str(e)}")
    chatbot_v2_instance = None
