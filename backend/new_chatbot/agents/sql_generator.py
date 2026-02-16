"""
SQL generation agent.
Generates MySQL queries from natural language questions.
"""
import json
import logging
from typing import Dict, Any, Optional, List
from groq import Groq

from ..config import config
from ..prompts import SQL_GENERATOR_PROMPT
from ..schema_context import schema_context

logger = logging.getLogger(__name__)


class SQLGenerator:
    """Generates SQL queries from natural language."""
    
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
        intent: Dict[str, Any],
        clarifications: Dict[str, str] = None,
        history: str = None,
        retry_count: int = 0,
        previous_error: str = None
    ) -> Dict[str, Any]:
        """
        Generate SQL query for a question.
        
        Args:
            question: The user's natural language question
            intent: Classified intent from IntentClassifier
            clarifications: Resolved clarifications from user
            history: Conversation history for context
            retry_count: Number of retry attempts (for error correction)
            previous_error: Error from previous attempt (for self-correction)
        
        Returns:
            {
                "sql": str,
                "explanation": str,
                "expected_columns": list,
                "query_type": str,
                "success": bool,
                "error": str or None
            }
        """
        clarifications_text = "None"
        if clarifications:
            clarifications_text = "\n".join([f"- {k}: {v}" for k, v in clarifications.items()])
        
        history_text = history if history else "No previous conversation"
        
        # Add error context for retries
        error_context = ""
        if previous_error and retry_count > 0:
            error_context = f"\n\nPREVIOUS ATTEMPT FAILED WITH ERROR:\n{previous_error}\n\nPlease correct the SQL to fix this error."
        
        prompt = SQL_GENERATOR_PROMPT.format(
            schema=self._get_schema_context(),
            history=history_text,
            question=question + error_context,
            intent=json.dumps(intent, indent=2),
            clarifications=clarifications_text
        )
        
        try:
            response = self.client.chat.completions.create(
                model=config.MODEL_SQL_GENERATOR,
                messages=[
                    {"role": "system", "content": "You are an expert MySQL query generator. Always respond in valid JSON with proper SQL syntax."},
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
            
            sql = result.get("sql", "").strip()
            
            # Basic safety check
            if not sql.upper().startswith("SELECT"):
                return {
                    "sql": None,
                    "explanation": "Only SELECT queries are allowed",
                    "expected_columns": [],
                    "query_type": "error",
                    "success": False,
                    "error": "Non-SELECT query generated"
                }
            
            # Print SQL to terminal for debugging
            print(f"\n{'='*60}")
            print(f"📝 GENERATED SQL:")
            print(f"{sql}")
            print(f"{'='*60}\n")
            
            return {
                "sql": sql,
                "explanation": result.get("explanation", ""),
                "expected_columns": result.get("expected_columns", []),
                "query_type": result.get("query_type", "select"),
                "success": True,
                "error": None
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse SQL generation response: {e}")
            return {
                "sql": None,
                "explanation": "",
                "expected_columns": [],
                "query_type": "error",
                "success": False,
                "error": f"JSON parsing error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"SQL generation error: {e}")
            return {
                "sql": None,
                "explanation": "",
                "expected_columns": [],
                "query_type": "error",
                "success": False,
                "error": str(e)
            }
    
    def generate_with_retry(
        self, 
        question: str,
        intent: Dict[str, Any],
        clarifications: Dict[str, str] = None,
        history: str = None,
        max_retries: int = 3
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
                clarifications=clarifications,
                history=history,
                retry_count=attempt,
                previous_error=last_error
            )
            
            if result["success"]:
                return result
            
            last_error = result.get("error", "Unknown error")
            logger.warning(f"SQL generation attempt {attempt + 1} failed: {last_error}")
        
        return {
            "sql": None,
            "explanation": "",
            "expected_columns": [],
            "query_type": "error",
            "success": False,
            "error": f"Failed after {max_retries} attempts. Last error: {last_error}"
        }


# Global instance
sql_generator = SQLGenerator()
