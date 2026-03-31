"""
Smart SQL Agent (v2)
Combines: SQL generation + self-validation
Single LLM call to generate and validate SQL.
"""
import json
import logging
from typing import Dict, Any, Optional
from groq import Groq

from ..config import config
from ..prompts import SMART_SQL_PROMPT
from ..schema_context import schema_context

logger = logging.getLogger(__name__)


class SmartSQL:
    """
    Generates SQL queries with self-validation.
    Single LLM call that both generates and validates the query.
    """
    
    def __init__(self):
        self.client = Groq(api_key=config.GROQ_API_KEY)
        self._schema_context: Optional[str] = None
    
    def _get_schema_context(self) -> str:
        """Get cached schema context."""
        if self._schema_context is None:
            self._schema_context = schema_context.get_full_schema_context()
        return self._schema_context
    
    def generate(
        self, 
        question: str,
        intent: str,
        entities: Dict[str, Any],
        tables: list,
        history: str = "No previous conversation.",
        clarifications: str = "None",
        retry_count: int = 0,
        previous_error: str = None
    ) -> Dict[str, Any]:
        """
        Generate SQL query with self-validation.
        
        Args:
            question: The user's natural language question
            intent: Classified intent (from unified analyzer)
            entities: Extracted entities (from unified analyzer)
            tables: Tables to query (from unified analyzer)
            history: Conversation history for context
            clarifications: Resolved clarifications from user
            retry_count: Number of retry attempts (for error correction)
            previous_error: Error from previous attempt (for self-correction)
        
        Returns:
            {
                "sql": str,
                "explanation": str,
                "is_valid": bool,
                "validation_notes": str,
                "success": bool,
                "error": str or None
            }
        """
        # Add error context for retries
        question_with_context = question
        if previous_error and retry_count > 0:
            question_with_context = f"{question}\n\n[PREVIOUS ATTEMPT FAILED: {previous_error}. Please correct the SQL.]"
        
        prompt = SMART_SQL_PROMPT.format(
            schema=self._get_schema_context(),
            question=question_with_context,
            intent=intent,
            entities=json.dumps(entities, indent=2),
            tables=json.dumps(tables),
            history=history,
            clarifications=clarifications
        )
        
        try:
            response = self.client.chat.completions.create(
                model=config.MODEL_SQL_GENERATOR,  # Best model for SQL
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert MySQL query generator. Respond only with valid JSON."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            result = json.loads(result_text)
            
            sql = (result.get("sql") or "").strip()
            
            # Basic safety check
            if not sql.upper().startswith("SELECT"):
                return {
                    "sql": None,
                    "explanation": "Only SELECT queries are allowed",
                    "is_valid": False,
                    "validation_notes": "Non-SELECT query generated",
                    "success": False,
                    "error": "Non-SELECT query generated"
                }
            
            # Log SQL for debugging
            logger.info(f"Generated SQL: {sql}")
            
            return {
                "sql": sql,
                "explanation": result.get("explanation", ""),
                "is_valid": result.get("is_valid", True),
                "validation_notes": result.get("validation_notes", ""),
                "success": True,
                "error": None
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse smart SQL response: {e}")
            return {
                "sql": None,
                "explanation": "",
                "is_valid": False,
                "validation_notes": "",
                "success": False,
                "error": f"JSON parsing error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Smart SQL error: {e}")
            return {
                "sql": None,
                "explanation": "",
                "is_valid": False,
                "validation_notes": "",
                "success": False,
                "error": str(e)
            }
    
    def generate_with_retry(
        self,
        question: str,
        intent: str,
        entities: Dict[str, Any],
        tables: list,
        history: str = "No previous conversation.",
        clarifications: str = "None",
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Generate SQL with automatic retry on failure.
        Uses self-correction by feeding error back to the model.
        """
        last_error = None
        
        for attempt in range(max_retries):
            result = self.generate(
                question=question,
                intent=intent,
                entities=entities,
                tables=tables,
                history=history,
                clarifications=clarifications,
                retry_count=attempt,
                previous_error=last_error
            )
            
            if result["success"]:
                return result
            
            last_error = result.get("error", "Unknown error")
            logger.warning(f"Smart SQL attempt {attempt + 1} failed: {last_error}")
        
        return {
            "sql": None,
            "explanation": "",
            "is_valid": False,
            "validation_notes": "",
            "success": False,
            "error": f"Failed after {max_retries} attempts. Last error: {last_error}"
        }


# Global instance
smart_sql = SmartSQL()
