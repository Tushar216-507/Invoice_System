"""
Response formatting agent.
Converts database query results into natural language responses.
"""
import json
import logging
from typing import Dict, Any, List, Optional
from groq import Groq

from ..config import config
from ..prompts import RESPONSE_FORMATTER_PROMPT

logger = logging.getLogger(__name__)


class ResponseFormatter:
    """Formats query results into natural language."""
    
    def __init__(self):
        self.client = Groq(api_key=config.GROQ_API_KEY)
    
    def format_response(
        self, 
        question: str,
        sql: str,
        results: List[Dict],
        columns: List[str]
    ) -> str:
        """
        Format query results into a natural language response.
        
        Args:
            question: Original user question
            sql: The executed SQL query
            results: List of result dictionaries
            columns: Column names in the results
        
        Returns:
            Formatted markdown response
        """
        # Handle empty results
        if not results:
            return self._format_empty_response(question)
        
        # For simple aggregates (single value), format directly
        if len(results) == 1 and len(results[0]) == 1:
            return self._format_single_value(question, results[0], columns)
        
        # For result sets up to 30 items, format as cards without LLM
        # This ensures amounts and details are properly shown
        if len(results) <= 30:
            return self._format_as_cards(question, results, columns)
        
        # Use LLM for very large or complex results
        return self._format_with_llm(question, sql, results, columns)
    
    def _format_empty_response(self, question: str) -> str:
        """Format response when no results found."""
        return (
            "📭 **No results found**\n\n"
            f"I couldn't find any data matching your query."
        )
    
    def _format_single_value(self, question: str, result: Dict, columns: List[str]) -> str:
        """Format a single aggregate value."""
        col = columns[0] if columns else list(result.keys())[0]
        value = result.get(col) or list(result.values())[0]
        
        # Format based on likely value type
        if isinstance(value, (int, float)):
            if value >= 1000:
                # Format as currency if looks like amount
                if any(word in question.lower() for word in ["amount", "total", "spent", "paid", "value"]):
                    formatted = f"₹{value:,.2f}"
                else:
                    formatted = f"{value:,}"
            else:
                formatted = str(value)
        else:
            formatted = str(value)
        
        return f"**Answer:** {formatted}"
    
    def _format_as_cards(self, question: str, results: List[Dict], columns: List[str]) -> str:
        """Format results as card-style text entries (no tables)."""
        lines = []
        
        # Columns to hide from display (internal/technical fields)
        HIDDEN_COLUMNS = {'id', 'vendor_id', 'pdf_path', 'deleted_at', 'deleted_by', 'po_id'}
        
        # Filter out hidden columns
        visible_columns = [col for col in columns if col.lower() not in HIDDEN_COLUMNS]
        
        # Check if user is asking for full/detailed info
        is_detail_request = any(word in question.lower() for word in ['full', 'detail', 'all info', 'complete', 'everything'])
        is_single_result = len(results) == 1
        
        # Summary line
        lines.append(f"**Found {len(results)} result(s):**\n")
        
        # Format each result as a card
        for row in results:
            # Get the primary identifier (invoice_number, po_number, vendor, or first column)
            primary_key = None
            primary_col = None
            for key in ['invoice_number', 'po_number', 'vendor', 'vendor_name', 'name']:
                if key in row and row[key]:
                    primary_key = row[key]
                    primary_col = key
                    break
            if not primary_key and visible_columns:
                primary_key = row.get(visible_columns[0], "Item")
                primary_col = visible_columns[0]
            
            # Build card entry
            lines.append(f"• **{primary_key}**")
            
            # Add details - show ALL for single result or detail requests
            for col in visible_columns:
                if col == primary_col:  # Skip the primary column since already shown
                    continue
                if col in row and row[col] is not None:
                    value = self._format_cell_value(row[col], col)
                    col_name = self._format_header(col)
                    
                    if is_single_result or is_detail_request:
                        # Show each field on its own line for detail view
                        lines.append(f"  - **{col_name}:** {value}")
                    else:
                        # Compact view for multiple results - collect first 3
                        pass  # Will be handled below
            
            # For multiple results (non-detail), show compact inline format
            if not is_single_result and not is_detail_request:
                details = []
                for col in visible_columns[:4]:  # Limit columns for compact view
                    if col == primary_col:
                        continue
                    if col in row and row[col] is not None:
                        value = self._format_cell_value(row[col], col)
                        col_name = self._format_header(col)
                        details.append(f"{col_name}: {value}")
                if details:
                    lines[-1] = f"• **{primary_key}** - " + " | ".join(details[:3])
            
            lines.append("")  # Add spacing between results
        
        return "\n".join(lines).strip()
    
    def _format_header(self, col: str) -> str:
        """Format column header for display."""
        # Convert snake_case to Title Case
        return col.replace("_", " ").title()
    
    def _format_cell_value(self, value: Any, column: str) -> str:
        """Format a cell value based on its type and column name."""
        if value is None:
            return "-"
        
        # Format amounts with currency
        if any(word in column.lower() for word in ["amount", "total", "gst", "cgst", "sgst", "rate"]):
            if isinstance(value, (int, float)):
                return f"₹{value:,.2f}"
        
        # Format dates
        if isinstance(value, str) and len(value) == 10 and "-" in value:
            try:
                from datetime import datetime
                dt = datetime.strptime(value, "%Y-%m-%d")
                return dt.strftime("%d %b %Y")
            except:
                pass
        
        return str(value)
    
    def _format_with_llm(
        self, 
        question: str, 
        sql: str, 
        results: List[Dict], 
        columns: List[str]
    ) -> str:
        """Use LLM to format complex results."""
        # Prepare results sample (limit for token efficiency)
        sample_results = results[:10]
        results_text = json.dumps(sample_results, indent=2, default=str)
        
        prompt = RESPONSE_FORMATTER_PROMPT.format(
            question=question,
            sql=sql,
            results=results_text,
            result_count=len(sample_results),
            total_rows=len(results)
        )
        
        try:
            # Use llama model which doesn't have thinking output issues
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",  # Fast model without thinking output
                messages=[
                    {"role": "system", "content": "You are a helpful data analyst. Output ONLY the final response in clean markdown. No thinking or reasoning."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=1500
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Strip any thinking tags that might appear
            result_text = self._strip_thinking_tags(result_text)
            
            return result_text
            
        except Exception as e:
            logger.error(f"Response formatting error: {e}")
            # Fallback to simple table format
            return self._format_as_table(question, results[:10], columns)
    
    def _strip_thinking_tags(self, text: str) -> str:
        """Remove any thinking/reasoning tags from LLM output."""
        import re
        # Remove <think>...</think> tags
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
        # Remove lines that start with "Okay," "Let me" etc. (common thinking patterns)
        lines = text.split('\n')
        cleaned_lines = []
        skip_until_table = False
        for line in lines:
            lower_line = line.strip().lower()
            # Skip lines that look like thinking
            if any(lower_line.startswith(pattern) for pattern in [
                'okay,', 'let me', 'first,', 'next,', 'i need to', 'the user',
                'looking at', 'wait,', 'so,', 'now,', 'checking', 'i should',
                'the query', 'based on', 'analyzing'
            ]):
                continue
            cleaned_lines.append(line)
        return '\n'.join(cleaned_lines).strip()


# Global instance
response_formatter = ResponseFormatter()
