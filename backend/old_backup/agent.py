"""
backend/agent.py - Enhanced HybridChatBot with Conversation Memory
Improvements:
1. Vendor shortform/name matching
2. Conversation context memory
3. Better response formatting
"""

from backend.ai_clients import (
    intent_analyzer,
    sql_generator,
    response_formatter,
    qwen_client,
)
from datetime import datetime
from typing import Dict, List, Optional
import logging
import uuid
import json

logger = logging.getLogger(__name__)


class HybridChatBot:
    """
    Enhanced hybrid chatbot with:
    - Vendor name/shortform matching
    - Conversation context memory
    - Improved response formatting
    """

    def __init__(self):
        self.conversations: Dict[str, Dict] = {}
        self.vendor_cache: List[Dict] = []
        self.vendor_cache_timestamp: Optional[datetime] = None
        self.vendor_cache_ttl: int = 3600

        self.user_cache: List[Dict] = []
        self.user_cache_timestamp: Optional[datetime] = None
        self.user_cache_ttl: int = 3600  # Cache for 1 hour
        
        logger.info("✅ HybridChatBot initialized with enhanced features")

    def cleanup_old_conversations(self):
        """Remove conversations older than 24 hours to prevent memory leak"""
        from datetime import datetime, timedelta
        
        cutoff = datetime.now() - timedelta(hours=24)
        to_remove = []
        
        for conv_id, conv_data in self.conversations.items():
            try:
                created = datetime.fromisoformat(conv_data.get('created_at', ''))
                if created < cutoff:
                    to_remove.append(conv_id)
            except (ValueError, TypeError):
                # Invalid timestamp, remove it
                to_remove.append(conv_id)
        
        for conv_id in to_remove:
            del self.conversations[conv_id]
        
        if to_remove:
            logger.info(f"🗑️ Cleaned up {len(to_remove)} old conversations")
    # ========================================================================
    # VENDOR MANAGEMENT
    # ========================================================================

    async def _load_vendors(self, force_refresh: bool = False) -> List[Dict]:
        """
        Load vendor list from database for matching

        Args:
        force_refresh: Force reload even if cache is valid
        
        Returns:
            List of vendor dictionaries
        """
        try:
            if (not force_refresh and 
                    self.vendor_cache and
                    self.vendor_cache_timestamp and
                    (datetime.now() - self.vendor_cache_timestamp).seconds < self.vendor_cache_ttl):
                    logger.info("✅ Using cached vendors (cache is fresh)")
                    return self.vendor_cache
            
            from backend.db import db_instance
            
            # Fetch all active vendors with their shortforms
            sql = """
            SELECT 
                id, 
                vendor_name, 
                shortforms_of_vendors,
                vendor_status
            FROM vendors 
            WHERE vendor_status = 'Active'
            ORDER BY vendor_name
            """
            
            vendors = db_instance.execute_query(sql)

            # ✅ EDIT 2: Validate that vendors were actually loaded
            if not vendors:
                logger.warning("⚠️ No active vendors found in database!")

                if self.vendor_cache:
                    logger.warning("⚠️ Keeping previous vendor cache")
                    return self.vendor_cache
                return []
            
            self.vendor_cache = vendors
            self.vendor_cache_timestamp = datetime.now()

            logger.info(f"✅ Loaded {len(vendors)} vendors into cache")
            return vendors
            
        except Exception as e:
            logger.error(f"❌ Failed to load vendors: {str(e)}")

            if self.vendor_cache:
                logger.warning("⚠️ Using stale vendor cache due to load error")
                return self.vendor_cache
            return []

    async def _load_users(self, force_refresh: bool = False) -> List[Dict]:
        """
        Load user list from database for matching
        
        Args:
            force_refresh: Force reload even if cache is valid
            
        Returns:
            List of user dictionaries
        """
        try:
            if (not force_refresh and 
                    self.user_cache and
                    self.user_cache_timestamp and
                    (datetime.now() - self.user_cache_timestamp).seconds < self.user_cache_ttl):
                    logger.info("✅ Using cached users (cache is fresh)")
                    return self.user_cache
            
            from backend.db import db_instance
            
            # Fetch all active users
            sql = """
            SELECT 
                id, 
                name, 
                email,
                role,
                department,
                is_active
            FROM users 
            WHERE is_active = 1
            ORDER BY name
            """
            
            users = db_instance.execute_query(sql)

            # Validate that users were actually loaded
            if not users:
                logger.warning("⚠️ No active users found in database!")
                
                if self.user_cache:
                    logger.warning("⚠️ Keeping previous user cache")
                    return self.user_cache
                return []
            
            self.user_cache = users
            self.user_cache_timestamp = datetime.now()

            logger.info(f"✅ Loaded {len(users)} users into cache")
            return users
            
        except Exception as e:
            logger.error(f"❌ Failed to load users: {str(e)}")
            
            if self.user_cache:
                logger.warning("⚠️ Using stale user cache due to load error")
                return self.user_cache
            return []
    # ========================================================================
    # LAYER 1: INTENT ANALYSIS (with context)
    # ========================================================================

    async def _layer1_intent_analysis(self, message: str, conversation_id: str) -> dict:
        """
        LAYER 1: Analyze user intent with conversation context
        """
        try:
            logger.info("⚙️ Layer 1: Intent Analysis (Qwen with Context)")

            if not intent_analyzer:
                logger.warning("Intent analyzer not available, defaulting to 'query'")
                return "query"

            # Get conversation history
            history = self.conversations.get(conversation_id, {}).get("history", [])
            history = history[-5:] if len(history) > 5 else history 
            
            intent_json = await intent_analyzer.analyze(message, history)
            logger.info(f"✅ Layer 1 complete - Intent: {intent_json}")
            return intent_json

        except Exception as e:
            logger.error(f"❌ Layer 1 failed: {str(e)}")
            return "query"

    # ========================================================================
    # LAYER 2: SQL GENERATION (with vendor matching and context)
    # ========================================================================

    async def _layer2_sql_generation(
        self, message: str, intent: str, schema: str, conversation_id: str
    ) -> str:
        """
        LAYER 2: Generate SQL with vendor matching and conversation context
        """
        try:
            logger.info("⚙️ Layer 2: SQL Generation (GPT-OSS with Context)")

            if not sql_generator:
                raise Exception("SQL generator not available")

            # Ensure vendors are loaded
            if not self.vendor_cache:
                await self._load_vendors()
                if not self.vendor_cache:
                    logger.warning("⚠️ No vendors loaded - vendor matching may not work")

            if not self.user_cache:
                await self._load_users()
                if not self.user_cache:
                    logger.warning("⚠️ No users loaded - user matching may not work")

            # Get conversation history
            history = self.conversations.get(conversation_id, {}).get("history", [])
            history = history[-5:] if len(history) > 5 else history

            sql = await sql_generator.generate(
                message, 
                intent, 
                schema, 
                conversation_history=history,
                vendor_list=self.vendor_cache,
                user_list=self.user_cache
            )

            # ADD THESE LINES immediately after the above call:
            logger.info(f"📊 Generated SQL length: {len(sql)} characters")
            logger.info(f"📊 SQL preview: {sql[:200]}...")

            # Check if it's a UNION query
            if 'UNION' in sql.upper():
                logger.info("📊 Query type: UNION (combined invoices + POs)")
            elif 'purchase_orders' in sql.lower():
                logger.info("📊 Query type: Purchase Orders only")
            else:
                logger.info("📊 Query type: Invoices only")

            logger.info(f"✅ Layer 2 complete - SQL: {sql[:150]}...")
            return sql

        except Exception as e:
            logger.error(f"❌ Layer 2 failed: {str(e)}")
            raise ValueError(f"Cannot generate SQL: {str(e)}")

    # ========================================================================
    # LAYER 3: QUERY EXECUTION
    # ========================================================================

    async def _layer3_execute_query(self, sql: str) -> List[Dict]:
        """
        LAYER 3: Execute SQL query on database
        """
        try:
            logger.info("⚙️ Layer 3: Query Execution")

            from backend.db import db_instance

            results = db_instance.execute_query(sql)

            logger.info(f"✅ Layer 3 complete - Got {len(results)} rows")
            return results

        except Exception as e:
            logger.error(f"❌ Layer 3 failed: {str(e)}")
            raise Exception(f"Query execution failed: {str(e)}")

    # ========================================================================
    # LAYER 4: RESPONSE FORMATTING (Enhanced)
    # ========================================================================

    async def _layer4_response_formatting(
        self, data: List[Dict], intent: str, message: str
    ) -> str:
        """
        LAYER 4: Format response with improved presentation
        """
        try:
            logger.info("⚙️ Layer 4: Response Formatting (Enhanced)")

            if not response_formatter:
                logger.warning("Response formatter not available, returning raw results")
                return f"Found {len(data)} matching records."

            response = await response_formatter.format(data, intent, message)

            logger.info("✅ Layer 4 complete - Response ready")
            return response

        except Exception as e:
            logger.error(f"❌ Layer 4 failed: {str(e)}")
            return f"Found {len(data)} matching records."

    # ========================================================================
    # MAIN PROCESS MESSAGE METHOD
    # ========================================================================

    async def process_message(
        self, message: str, conversation_id: Optional[str] = None
    ) -> Dict:
        """
        Process message through 4-layer pipeline with enhanced features
        """
        try:
            # Clean Up old conversations for avoiding context rotting
            if len(self.conversations)>100:
                self.cleanup_old_conversations()

            logger.info("=" * 70)
            logger.info("📨 NEW MESSAGE RECEIVED")
            logger.info(f"Message: {message[:100]}")
            logger.info("=" * 70)

            if not conversation_id:
                conversation_id = self._create_conversation()

            # Load vendors if not already loaded
            if not self.vendor_cache:
                await self._load_vendors()

            if not self.user_cache:
                await self._load_users()



            # ================================================================
            # LAYER 1: Intent Analysis (with context)
            # ================================================================
            logger.info("\n" + "=" * 70)
            logger.info("🟢 LAYER 1: INTENT ANALYSIS (WITH CONTEXT)")
            logger.info("=" * 70)

            intent_json = await self._layer1_intent_analysis(message, conversation_id)

            logger.info(f"✅ Intent: {intent_json}\n")
            if intent_json.get("entity_type") == "user":
                logger.info(f"🧑 USER QUERY DETECTED")
                logger.info(f"   Query Type: {intent_json.get('user_query_type')}")
                
                # Try to extract user name from message
                if self.user_cache:
                    mentioned_users = []
                    message_lower = message.lower()
                    for user in self.user_cache:
                        if user['name'].lower() in message_lower:
                            mentioned_users.append(user['name'])
                    
                    if mentioned_users:
                        logger.info(f"   Mentioned Users: {', '.join(mentioned_users)}")
                    else:
                        logger.info(f"   ⚠️ No matching users found in cache!")

            # Intent is now always a dict
            intent_value = intent_json.get("primary_intent", "query")
            requires_aggregation = intent_json.get("requires_aggregation", False)
            entity_type = intent_json.get("entity_type", "invoice")

            # ================================================================
            # LAYER 2: SQL Generation (with vendor matching and context)
            # ================================================================
            logger.info("=" * 70)
            logger.info("🟨 LAYER 2: SQL GENERATION (WITH VENDOR MATCHING)")
            logger.info("=" * 70)

            from backend.db import db_instance

            schema = db_instance.get_schema()

            try:
                sql = await self._layer2_sql_generation(
                    message, intent_value, schema, conversation_id
                )
            except Exception as e:
                logger.error(f"SQL generation failed: {str(e)}")
                 # ✅ Provide helpful error message for user queries
                error_msg = f"Error generating query: {str(e)}"
                
                if intent_value == "user" or "user" in message.lower():
                    # Check if user name might be misspelled
                    mentioned_words = [w for w in message.split() if len(w) > 2 and w.isalpha()]
                    
                    if self.user_cache:
                        possible_matches = []
                        for word in mentioned_words:
                            for user in self.user_cache:
                                if word.lower() in user['name'].lower():
                                    possible_matches.append(f"{user['name']} ({user.get('department', 'N/A')})")
                        
                        if possible_matches:
                            error_msg = (
                                f"I couldn't process your user query. Did you mean one of these users?\n"
                                f"{', '.join(set(possible_matches[:5]))}"
                            )
                        else:
                            error_msg = (
                                "I couldn't find that user. Please check the spelling or try using their full name."
                            )

                return {
                    "response":error_msg,
                    "data": [],
                    "conversation_id": conversation_id,
                    "error": True,
                    "layers": {"intent_json": intent_json},
                }

            logger.info(f"✅ SQL: {sql}\n")

            # ================================================================
            # LAYER 3: Query Execution
            # ================================================================
            logger.info("=" * 70)
            logger.info("🔵 LAYER 3: QUERY EXECUTION")
            logger.info("=" * 70)

            try:
                data = await self._layer3_execute_query(sql)
            except Exception as e:
                logger.error(f"Query execution failed: {str(e)}")
                return {
                    "response": f"Error executing query: {str(e)}",
                    "data": [],
                    "conversation_id": conversation_id,
                    "error": True,
                    "layers": {"intent_json": intent_json, "sql": sql},
                }

            logger.info(f"✅ Results: {len(data)} rows\n")

            # ================================================================
            # LAYER 4: Response Formatting (Enhanced)
            # ================================================================
            logger.info("=" * 70)
            logger.info("🟣 LAYER 4: RESPONSE FORMATTING (ENHANCED)")
            logger.info("=" * 70)

            response = await self._layer4_response_formatting(
                data, intent_value, message
            )

            logger.info(f"✅ Response: {response[:150]}...\n")

            # ================================================================
            # Save to conversation history with full context
            # ================================================================
            # ✅ Extract user mentions from the message
            user_mentions = []
            if self.user_cache and intent_value in ["user", "user_query"]:
                message_lower = message.lower()
                for user in self.user_cache:
                    user_name_lower = user['name'].lower()
                    if user_name_lower in message_lower:
                        user_mentions.append({
                            "name": user['name'],
                            "email": user.get('email'),
                            "role": user.get('role'),
                            "department": user.get('department')
                        })

            self.conversations[conversation_id]["history"].append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "user": message,
                    "bot": response,
                    "data_count": len(data),
                    "intent": intent_value,
                    "sql": sql,
                    "user_mentions": user_mentions,
                    "entity_type": entity_type,
                    "user_query": intent_value in ["user", "user_query"],
                }
            )

            logger.info("=" * 70)
            logger.info("✅ MESSAGE PROCESSING COMPLETE")
            logger.info("=" * 70 + "\n")

            return {
                "response": response,
                "data": data,
                "conversation_id": conversation_id,
                "error": False,
                "layers": {
                    "intent_json": intent_json,
                    "sql": sql,
                    "data_count": len(data),
                },
            }

        except Exception as e:
            logger.error(f"❌ Fatal error in process_message: {str(e)}")
            return {
                "response": f"System error: {str(e)}",
                "data": [],
                "conversation_id": conversation_id or "unknown",
                "error": True,
                "layers": {},
            }

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _create_conversation(self) -> str:
        """Create new conversation ID with empty history"""
        conv_id = str(uuid.uuid4())
        self.conversations[conv_id] = {
            "created_at": datetime.now().isoformat(),
            "history": [],
        }
        logger.info(f"📌 New conversation: {conv_id}")
        return conv_id

    def get_conversation_history(self, conversation_id: str) -> Dict:
        """Get conversation history"""
        return self.conversations.get(conversation_id, {})

    def list_conversations(self) -> List[str]:
        """List all conversation IDs"""
        return list(self.conversations.keys())

    def clear_conversation(self, conversation_id: str) -> bool:
        """Clear a specific conversation"""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            logger.info(f"🗑️ Cleared conversation: {conversation_id}")
            return True
        return False


# ============================================================================
# CREATE GLOBAL INSTANCE
# ============================================================================

try:
    chatbot_instance = HybridChatBot()
    logger.info("✅ Enhanced ChatBot instance created")
except Exception as e:
    logger.error(f"❌ ChatBot init failed: {str(e)}")
    chatbot_instance = None