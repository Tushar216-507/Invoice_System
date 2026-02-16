"""
Ambiguity detection agent.
Analyzes user questions to detect ambiguity and generate clarifying questions.
"""
import json
import logging
import re
from typing import Dict, Any, Optional, Tuple, List
from groq import Groq

from ..config import config
from ..prompts import AMBIGUITY_DETECTOR_PROMPT, CLARIFICATION_PARSER_PROMPT
from ..schema_context import schema_context
from ..database import db

logger = logging.getLogger(__name__)


class AmbiguityDetector:
    """Detects ambiguous questions and generates clarifications."""
    
    def __init__(self):
        self.client = Groq(api_key=config.GROQ_API_KEY)
        self._schema_context: Optional[str] = None
        self._user_names_cache: Optional[List[str]] = None
        self._vendor_names_cache: Optional[List[str]] = None
    
    def _get_schema_context(self) -> str:
        """Get cached schema context."""
        if self._schema_context is None:
            self._schema_context = schema_context.get_full_schema_context()
        return self._schema_context
    
    def _load_known_names(self) -> None:
        """Load user and vendor names from database for collision detection."""
        if self._user_names_cache is None:
            try:
                # Get user names
                user_results, _ = db.execute_query("SELECT DISTINCT name FROM users WHERE name IS NOT NULL")
                self._user_names_cache = [row['name'].lower() for row in user_results if row.get('name')]
                
                # Also get unique first names from created_by, approved_by, reviewed_by in invoices
                invoice_creators, _ = db.execute_query("""
                    SELECT DISTINCT created_by as name FROM invoices WHERE created_by IS NOT NULL
                    UNION SELECT DISTINCT approved_by FROM invoices WHERE approved_by IS NOT NULL
                    UNION SELECT DISTINCT reviewed_by FROM invoices WHERE reviewed_by IS NOT NULL
                """)
                for row in invoice_creators:
                    if row.get('name'):
                        self._user_names_cache.append(row['name'].lower())
                
                self._user_names_cache = list(set(self._user_names_cache))
            except Exception as e:
                logger.error(f"Failed to load user names: {e}")
                self._user_names_cache = []
        
        if self._vendor_names_cache is None:
            try:
                vendor_results, _ = db.execute_query("SELECT DISTINCT vendor_name FROM vendors WHERE vendor_name IS NOT NULL")
                self._vendor_names_cache = [row['vendor_name'].lower() for row in vendor_results if row.get('vendor_name')]
                
                # Also get vendor names from invoices
                invoice_vendors, _ = db.execute_query("SELECT DISTINCT vendor FROM invoices WHERE vendor IS NOT NULL")
                for row in invoice_vendors:
                    if row.get('vendor'):
                        self._vendor_names_cache.append(row['vendor'].lower())
                
                self._vendor_names_cache = list(set(self._vendor_names_cache))
            except Exception as e:
                logger.error(f"Failed to load vendor names: {e}")
                self._vendor_names_cache = []
    
    def _extract_potential_names(self, question: str) -> List[str]:
        """Extract potential person/company names from a question."""
        # Comprehensive list of stop words that should NEVER be treated as names
        stop_words = {
            # Common verbs/actions
            'show', 'list', 'find', 'get', 'all', 'give', 'tell', 'what', 'how', 'when', 'where',
            'created', 'approved', 'reviewed', 'processed', 'made', 'done', 'sent', 
            # Conjunctions and prepositions
            'and', 'or', 'the', 'a', 'an', 'of', 'for', 'to', 'from', 'by', 'with', 'in', 'on', 'at',
            # Invoice related terms
            'invoices', 'invoice', 'pending', 'cleared', 'paid', 'unpaid', 'amount', 'total', 'value',
            'purchase', 'orders', 'order', 'po', 'pos', 'details', 'detail', 'data', 'info', 'information',
            # Entity types
            'vendor', 'vendors', 'user', 'users', 'department', 'departments', 'company', 'companies',
            # Time words
            'today', 'yesterday', 'this', 'last', 'next', 'month', 'year', 'week', 'day', 'date',
            'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 
            'september', 'october', 'november', 'december', 'fy',
            # Numbers written as words
            'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
            'first', 'second', 'third', 'many', 'much', 'any', 'some',
            # Status words
            'status', 'pending', 'approved', 'rejected', 'completed', 'active', 'inactive',
            # Common query words
            'top', 'bottom', 'latest', 'oldest', 'recent', 'new', 'old', 'highest', 'lowest',
            'between', 'more', 'less', 'than', 'above', 'below', 'over', 'under'
        }
        
        # Split and filter
        words = question.lower().split()
        potential_names = []
        
        # Look for capitalized words in original question (likely names)
        original_words = question.split()
        for word in original_words:
            clean_word = re.sub(r'[^\w]', '', word)
            # Must be at least 3 characters and not a stop word
            if clean_word and len(clean_word) >= 3 and clean_word[0].isupper():
                if clean_word.lower() not in stop_words:
                    potential_names.append(clean_word.lower())
        
        # Also check remaining words (but be more strict - only if longer than 4 chars)
        for word in words:
            clean_word = re.sub(r'[^\w]', '', word)
            if clean_word and len(clean_word) > 4 and clean_word not in stop_words:
                # Only add if it looks like a name (not all lowercase common word)
                if clean_word not in potential_names:
                    potential_names.append(clean_word)
        
        return list(set(potential_names))
    
    def check_name_collision(self, question: str) -> Tuple[bool, str, str]:
        """
        Check if any name in the question exists in BOTH users and vendors.
        
        Returns:
            (has_collision: bool, matched_name: str, collision_type: str)
        """
        self._load_known_names()
        potential_names = self._extract_potential_names(question)
        
        for name in potential_names:
            # Check if name matches any user
            user_match = any(name in user_name for user_name in self._user_names_cache)
            
            # Check if name matches any vendor
            vendor_match = any(name in vendor_name for vendor_name in self._vendor_names_cache)
            
            if user_match and vendor_match:
                return True, name, "name_exists_in_both"
        
        return False, "", "no_collision"
    
    def _is_clear_vendor_query(self, question: str) -> bool:
        """Check if question clearly refers to a vendor based on phrase patterns."""
        vendor_patterns = [
            r'invoices?\s+from\s+',
            r'paid\s+to\s+',
            r'payments?\s+to\s+',
            r'purchase\s+orders?\s+(to|from|for)\s+',
            r'vendor\s+',
            r'po\s+(to|from|for)\s+',
        ]
        q_lower = question.lower()
        return any(re.search(pattern, q_lower) for pattern in vendor_patterns)
    
    def _is_clear_user_query(self, question: str) -> bool:
        """Check if question clearly refers to a user based on phrase patterns."""
        user_patterns = [
            r'(created|approved|reviewed|processed)\s+by\s+\w+',
            r'\bby\s+user\s+',
            r'invoices?\s+by\s+\w+',  # "invoices by Hemant"
            r'\w+\s+(created|approved|reviewed|processed)\s+',  # "Hemant created"
            r'what\s+did\s+\w+\s+(create|process|approve|review)',  # "what did Mrunal create"
        ]
        q_lower = question.lower()
        return any(re.search(pattern, q_lower) for pattern in user_patterns)
    
    def detect_ambiguity(
        self, 
        question: str, 
        history: str = "No previous conversation."
    ) -> Dict[str, Any]:
        """
        Analyze a question for ambiguity using HYBRID approach.
        
        Hybrid Logic:
        1. Check if any name in the question exists in BOTH users and vendors
        2. If no collision found, use phrase patterns to determine intent
        3. Only ask clarification if collision is detected AND patterns don't resolve
        
        Returns:
            {
                "is_ambiguous": bool,
                "ambiguity_type": str,
                "confidence": float,
                "clarifying_question": str or None,
                "options": list of str,
                "reasoning": str
            }
        """
        # STEP 1: Check for name collision in database
        has_collision, matched_name, collision_type = self.check_name_collision(question)
        
        if has_collision:
            # Check if phrase patterns can resolve the ambiguity
            is_vendor = self._is_clear_vendor_query(question)
            is_user = self._is_clear_user_query(question)
            
            if is_vendor and not is_user:
                # Clear vendor query pattern - no need to ask
                logger.info(f"Name collision detected for '{matched_name}', but phrase pattern indicates VENDOR")
                return {
                    "is_ambiguous": False,
                    "ambiguity_type": "none",
                    "confidence": 0.85,
                    "clarifying_question": None,
                    "options": [],
                    "reasoning": f"Name '{matched_name}' exists in both users and vendors, but 'from/to' pattern indicates vendor query"
                }
            elif is_user and not is_vendor:
                # Clear user query pattern - no need to ask
                logger.info(f"Name collision detected for '{matched_name}', but phrase pattern indicates USER")
                return {
                    "is_ambiguous": False,
                    "ambiguity_type": "none",
                    "confidence": 0.85,
                    "clarifying_question": None,
                    "options": [],
                    "reasoning": f"Name '{matched_name}' exists in both users and vendors, but 'by/created/approved' pattern indicates user query"
                }
            else:
                # Collision detected AND patterns don't resolve - MUST ask clarification
                logger.info(f"Name collision detected for '{matched_name}' - asking for clarification")
                return {
                    "is_ambiguous": True,
                    "ambiguity_type": "entity_confusion",
                    "confidence": 0.95,
                    "clarifying_question": f"'{matched_name.title()}' exists as both a user and a vendor in the database. Are you asking about invoices created/processed by the user '{matched_name.title()}' or invoices from the vendor '{matched_name.title()}'?",
                    "options": [f"User {matched_name.title()}", f"Vendor {matched_name.title()}", "Both"],
                    "reasoning": f"The name '{matched_name}' exists in both users and vendors tables, and the question pattern doesn't clearly indicate which one"
                }
        
        # STEP 2: No collision - use LLM for other types of ambiguity (scope, date range, etc.)
        prompt = AMBIGUITY_DETECTOR_PROMPT.format(
            schema=self._get_schema_context(),
            question=question,
            history=history
        )
        
        try:
            response = self.client.chat.completions.create(
                model=config.MODEL_AMBIGUITY_DETECTOR,
                messages=[
                    {"role": "system", "content": "You are an ambiguity detection expert. Always respond in valid JSON."},
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
            
            # Validate and ensure required fields
            return {
                "is_ambiguous": result.get("is_ambiguous", False),
                "ambiguity_type": result.get("ambiguity_type", "none"),
                "confidence": result.get("confidence", 0.0),
                "clarifying_question": result.get("clarifying_question"),
                "options": result.get("options", []),
                "reasoning": result.get("reasoning", "")
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse ambiguity detection response: {e}")
            # Default to not ambiguous if parsing fails
            return {
                "is_ambiguous": False,
                "ambiguity_type": "none",
                "confidence": 0.0,
                "clarifying_question": None,
                "options": [],
                "reasoning": "Failed to analyze question"
            }
        except Exception as e:
            logger.error(f"Ambiguity detection error: {e}")
            return {
                "is_ambiguous": False,
                "ambiguity_type": "none",
                "confidence": 0.0,
                "clarifying_question": None,
                "options": [],
                "reasoning": f"Error: {str(e)}"
            }
    
    def parse_clarification_response(
        self,
        original_question: str,
        clarifying_question: str,
        options: list,
        user_response: str
    ) -> Dict[str, Any]:
        """
        Parse user's response to a clarification question.
        
        Returns:
            {
                "selected_option_index": int,
                "selected_option_text": str,
                "confidence": float,
                "parsed_successfully": bool
            }
        """
        # First try simple matching (numbers 1, 2, 3 or option text)
        user_response_lower = user_response.strip().lower()
        
        # Check for number responses
        for i, option in enumerate(options):
            if user_response_lower == str(i + 1):
                return {
                    "selected_option_index": i,
                    "selected_option_text": option,
                    "confidence": 1.0,
                    "parsed_successfully": True
                }
        
        # Check for text match
        for i, option in enumerate(options):
            if user_response_lower in option.lower() or option.lower() in user_response_lower:
                return {
                    "selected_option_index": i,
                    "selected_option_text": option,
                    "confidence": 0.9,
                    "parsed_successfully": True
                }
        
        # Use LLM for complex responses
        options_text = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(options)])
        
        prompt = CLARIFICATION_PARSER_PROMPT.format(
            original_question=original_question,
            clarifying_question=clarifying_question,
            options=options_text,
            user_response=user_response
        )
        
        try:
            response = self.client.chat.completions.create(
                model=config.MODEL_AMBIGUITY_DETECTOR,
                messages=[
                    {"role": "system", "content": "You are a response parser. Always respond in valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=500
            )
            
            result_text = response.choices[0].message.content.strip()
            
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            result = json.loads(result_text)
            return result
            
        except Exception as e:
            logger.error(f"Clarification parsing error: {e}")
            return {
                "selected_option_index": 0,
                "selected_option_text": options[0] if options else "",
                "confidence": 0.0,
                "parsed_successfully": False
            }


# Global instance
ambiguity_detector = AmbiguityDetector()
