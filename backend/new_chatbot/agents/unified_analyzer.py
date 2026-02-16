"""
Unified Analyzer Agent (v2)
Combines: ambiguity detection + intent classification + entity extraction
Single LLM call to analyze user questions.
Includes hybrid name collision detection for vendor/user ambiguity.
"""
import json
import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from groq import Groq

from ..config import config
from ..prompts import UNIFIED_ANALYZER_PROMPT
from ..schema_context import schema_context
from ..database import db

logger = logging.getLogger(__name__)


class UnifiedAnalyzer:
    """
    Analyzes user questions in a single LLM call.
    Determines intent, extracts entities, and decides if clarification is needed.
    Uses hybrid approach: rule-based name collision check + LLM for complex cases.
    """
    
    def __init__(self):
        self.client = Groq(api_key=config.GROQ_API_KEY)
        self._schema_summary: Optional[str] = None
        # Cache for name lookups
        self._vendor_data: Optional[Dict[str, str]] = None  # first_name -> full_name
        self._user_data: Optional[Dict[str, str]] = None    # first_name -> full_name
    
    def _get_vendor_data(self) -> Dict[str, str]:
        """Cache vendor first names mapped to full names."""
        if self._vendor_data is None:
            self._vendor_data = {}
            try:
                results, _ = db.execute_query("SELECT vendor_name FROM vendors WHERE vendor_name IS NOT NULL")
                for r in results:
                    full_name = r.get('vendor_name', '')
                    if full_name:
                        # Extract first word as primary identifier
                        first_word = full_name.split()[0].lower()
                        self._vendor_data[first_word] = full_name
            except Exception as e:
                logger.error(f"Failed to fetch vendor names: {e}")
        return self._vendor_data
    
    def _get_user_data(self) -> Dict[str, str]:
        """Cache user first names mapped to full names."""
        if self._user_data is None:
            self._user_data = {}
            try:
                results, _ = db.execute_query("SELECT name FROM users WHERE name IS NOT NULL")
                for r in results:
                    full_name = r.get('name', '')
                    if full_name:
                        # Extract first word as primary identifier
                        first_word = full_name.split()[0].lower()
                        self._user_data[first_word] = full_name
            except Exception as e:
                logger.error(f"Failed to fetch user names: {e}")
        return self._user_data
    
    def _check_name_collision(self, question: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Check if any name in the question exists in BOTH vendors AND users.
        Uses first-name matching for accuracy.
        
        Returns: (has_collision, matched_word, vendor_name, user_name)
        """
        vendors = self._get_vendor_data()
        users = self._get_user_data()
        
        if not vendors or not users:
            return False, None, None, None
        
        # Find names that exist in BOTH vendors and users
        shared_first_names = set(vendors.keys()) & set(users.keys())
        
        if not shared_first_names:
            # No overlap - no collision possible
            return False, None, None, None
        
        # Extract words from question (min 4 chars to avoid matching "the", "and", etc.)
        q_lower = question.lower()
        words = set(re.findall(r'\b[a-zA-Z]{4,}\b', q_lower))
        
        # Check if any shared first name is mentioned
        for shared_name in shared_first_names:
            if shared_name in words:
                vendor_full = vendors[shared_name]
                user_full = users[shared_name]
                logger.info(f"Name collision: '{shared_name}' -> Vendor: {vendor_full}, User: {user_full}")
                return True, shared_name.title(), vendor_full, user_full
        
        return False, None, None, None
    
    def _is_context_clear(self, question: str) -> bool:
        """Check if the question has clear context about vendor vs user."""
        q_lower = question.lower()
        
        # Clear vendor indicators
        vendor_patterns = [
            'from vendor', 'vendor called', 'vendor named', 'supplier',
            'the vendor', 'vendor ', 'from the vendor'
        ]
        # Clear user indicators
        user_patterns = [
            'created by', 'approved by', 'reviewed by', 'processed by',
            'user called', 'user named', 'employee',
            'the user', 'by the user', 'from user'
        ]
        
        for pattern in vendor_patterns:
            if pattern in q_lower:
                return True
        for pattern in user_patterns:
            if pattern in q_lower:
                return True
        
        return False
    
    def _get_schema_summary(self) -> str:
        """Get a brief schema summary for the prompt."""
        if self._schema_summary is None:
            # Create a concise schema summary instead of full 9KB schema
            self._schema_summary = """
TABLES:
- invoices: id, invoice_number, vendor, total_amount, gst, invoice_date, date_received, 
  invoice_cleared (Yes/No), po_number, created_by, approved_by, reviewed_by, 
  hod_values, ceo_values, department, deleted_at,deleted_by
  
- purchase_orders: id, po_number (format: FY25-26/XXX-DATE/N), vendor_id, 
  total_amount, cgst_amount, sgst_amount, grand_total, po_date, 
  created_by, approved_by, reviewed_by, deleted_at
  
- vendors: id, vendor_name, vendor_status (Active/Inactive), department, 
  shortforms_of_vendors (e.g., "NCS" for "Nimayate Corporate Solutions"), PAN, GSTIN, POC, POC_email,deleted_at

- users: id, name, email, role (user/admin/hod/ceo), department, is_active

- vendor_requests: id,vendor_name,vendor_status,department,description,vendor_address,PAN,
  POC,POC_number,POC_email,requested_by_name,requested_by_email,request_date,status,reviewed_by_user_id,reviewed_by_name,reviewed_date,rejection_reason

KEY RELATIONSHIPS:
- invoices.vendor = vendors.vendor_name
- invoices.po_number links to purchase_orders.po_number
- created_by/approved_by/reviewed_by in invoices = user full names like "Mrunal Salvi"

⚠️ NOTE: Users often type SHORTFORMS or PARTIAL names:
- "shyju" means "Shyjumon Thomas"
- "ncs" means "Nimayate Corporate Solutions"
- Always consider partial name matching in your analysis
"""
        return self._schema_summary
    
    def analyze(
        self, 
        question: str, 
        history: str = "No previous conversation.",
        skip_collision_check: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze a user question and return structured analysis.
        Uses hybrid approach: check name collisions first, then LLM for complex cases.
        
        Args:
            question: The user's question
            history: Conversation history for context
            skip_collision_check: If True, skip the name collision check (used after clarification)
        
        Returns:
            {
                "can_proceed": bool,
                "clarification": None or {"question": str, "options": list},
                "intent": str,
                "entities": dict,
                "tables": list,
                "reasoning": str
            }
        """
        # STEP 1: Check for name collision (vendor vs user) - unless skipped
        if not skip_collision_check:
            has_collision, matched_name, vendor_full, user_full = self._check_name_collision(question)
            
            if has_collision and not self._is_context_clear(question):
                # Found a name that exists in both vendors and users, and context is unclear
                logger.info(f"Asking clarification for name collision: {matched_name}")
                return {
                    "can_proceed": False,
                    "clarification": {
                        "question": f"I found '{matched_name}' as both a vendor ({vendor_full}) and a user ({user_full}). Which one do you mean?",
                        "options": [f"Vendor: {vendor_full}", f"User: {user_full}", "Both"]
                    },
                    "intent": "invoice_query",
                    "entities": {"ambiguous_name": matched_name, "vendor_full": vendor_full, "user_full": user_full},
                    "tables": ["invoices"],
                    "reasoning": f"Name '{matched_name}' exists in both vendors ({vendor_full}) and users ({user_full})"
                }
        
        # STEP 2: Use LLM for complex analysis
        prompt = UNIFIED_ANALYZER_PROMPT.format(
            schema_summary=self._get_schema_summary(),
            question=question,
            history=history
        )
        
        try:
            response = self.client.chat.completions.create(
                model=config.MODEL_INTENT_CLASSIFIER,  # Using versatile model for good reasoning
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a question analyzer. Respond only with valid JSON."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            result = json.loads(result_text)
            
            # Validate and ensure required fields with defaults
            return {
                "can_proceed": result.get("can_proceed", True),
                "clarification": result.get("clarification"),
                "intent": result.get("intent", "invoice_query"),
                "entities": result.get("entities", {}),
                "tables": result.get("tables", ["invoices"]),
                "reasoning": result.get("reasoning", "")
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse unified analyzer response: {e}")
            # Default to proceeding with basic intent
            return self._default_analysis(question)
        except Exception as e:
            logger.error(f"Unified analyzer error: {e}")
            return self._default_analysis(question)
    
    def _default_analysis(self, question: str) -> Dict[str, Any]:
        """Return default analysis when LLM call fails."""
        # Simple keyword-based fallback
        q_lower = question.lower()
        
        intent = "invoice_query"
        tables = ["invoices"]
        
        if "vendor" in q_lower:
            intent = "vendor_query"
            tables = ["vendors"]
        elif "po" in q_lower or "purchase order" in q_lower:
            intent = "po_query"
            tables = ["purchase_orders"]
        elif "user" in q_lower:
            intent = "user_query"
            tables = ["users"]
        
        return {
            "can_proceed": True,
            "clarification": None,
            "intent": intent,
            "entities": {},
            "tables": tables,
            "reasoning": "Fallback analysis used"
        }
    
    def parse_clarification_response(
        self,
        options: List[str],
        user_response: str
    ) -> Dict[str, Any]:
        """
        Parse user's response to a clarification question.
        Uses simple matching - no LLM call needed.
        """
        user_response_lower = user_response.strip().lower()
        
        # Check for number responses (1, 2, 3)
        for i, option in enumerate(options):
            if user_response_lower == str(i + 1):
                return {
                    "selected_option_index": i,
                    "selected_option_text": option,
                    "parsed_successfully": True
                }
        
        # Check for text match
        for i, option in enumerate(options):
            option_lower = option.lower()
            if user_response_lower in option_lower or option_lower in user_response_lower:
                return {
                    "selected_option_index": i,
                    "selected_option_text": option,
                    "parsed_successfully": True
                }
        
        # Couldn't match - return first option as default
        return {
            "selected_option_index": 0,
            "selected_option_text": options[0] if options else "",
            "parsed_successfully": False
        }


# Global instance
unified_analyzer = UnifiedAnalyzer()
