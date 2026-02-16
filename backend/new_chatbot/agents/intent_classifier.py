"""
Intent classification agent.
Classifies user questions and extracts relevant entities.
"""
import json
import logging
from typing import Dict, Any, List, Optional
from groq import Groq

from ..config import config
from ..prompts import INTENT_CLASSIFIER_PROMPT
from ..schema_context import schema_context

logger = logging.getLogger(__name__)


class IntentClassifier:
    """Classifies user intents and extracts entities."""
    
    def __init__(self):
        self.client = Groq(api_key=config.GROQ_API_KEY)
        self._schema_context: Optional[str] = None
    
    def _get_schema_context(self) -> str:
        """Get cached schema context."""
        if self._schema_context is None:
            self._schema_context = schema_context.get_full_schema_context()
        return self._schema_context
    
    def classify(
        self, 
        question: str, 
        context: str = ""
    ) -> Dict[str, Any]:
        """
        Classify user intent and extract entities.
        
        Returns:
            {
                "primary_intent": str,
                "secondary_intent": str or None,
                "tables_involved": list,
                "entities": dict,
                "filters": dict,
                "aggregation_type": str,
                "sort_by": str or None,
                "limit": int or None
            }
        """
        prompt = INTENT_CLASSIFIER_PROMPT.format(
            schema=self._get_schema_context(),
            question=question,
            context=context or "No additional context."
        )
        
        try:
            response = self.client.chat.completions.create(
                model=config.MODEL_INTENT_CLASSIFIER,
                messages=[
                    {"role": "system", "content": "You are an intent classification expert. Always respond in valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            result = json.loads(result_text)
            
            # Ensure all required fields exist
            return {
                "primary_intent": result.get("primary_intent", "invoice_query"),
                "secondary_intent": result.get("secondary_intent"),
                "tables_involved": result.get("tables_involved", ["invoices"]),
                "entities": result.get("entities", {}),
                "filters": result.get("filters", {}),
                "aggregation_type": result.get("aggregation_type", "list"),
                "sort_by": result.get("sort_by"),
                "limit": result.get("limit")
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse intent classification response: {e}")
            return self._default_intent()
        except Exception as e:
            logger.error(f"Intent classification error: {e}")
            return self._default_intent()
    
    def _default_intent(self) -> Dict[str, Any]:
        """Return default intent when classification fails."""
        return {
            "primary_intent": "invoice_query",
            "secondary_intent": None,
            "tables_involved": ["invoices"],
            "entities": {},
            "filters": {},
            "aggregation_type": "list",
            "sort_by": None,
            "limit": 100
        }


# Global instance
intent_classifier = IntentClassifier()
