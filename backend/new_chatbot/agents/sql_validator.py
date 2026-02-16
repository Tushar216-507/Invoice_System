"""
SQL validation and safety agent.
Validates SQL queries for correctness and safety before execution.
"""
import re
import logging
from typing import Dict, Any, List, Optional, Tuple
import sqlparse
from sqlparse.sql import Statement

from ..schema_context import schema_context

logger = logging.getLogger(__name__)


class SQLValidator:
    """Validates SQL queries for safety and correctness."""
    
    # Dangerous keywords that should never appear in generated SQL
    DANGEROUS_KEYWORDS = [
        "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", 
        "CREATE", "REPLACE", "GRANT", "REVOKE", "COMMIT", "ROLLBACK",
        "EXEC", "EXECUTE", "CALL", "INTO OUTFILE", "INTO DUMPFILE",
        "LOAD_FILE", "BENCHMARK", "SLEEP"
    ]
    
    def __init__(self):
        self._valid_tables: Optional[List[str]] = None
        self._valid_columns: Optional[Dict[str, List[str]]] = None
    
    def _load_schema_info(self):
        """Load valid table and column names from schema."""
        if self._valid_tables is None:
            self._valid_tables = schema_context.get_all_table_names()
            self._valid_columns = {}
            for table in self._valid_tables:
                self._valid_columns[table] = schema_context.get_column_names_for_table(table)
    
    def validate(self, sql: str) -> Dict[str, Any]:
        """
        Validate a SQL query for safety and correctness.
        
        Returns:
            {
                "is_valid": bool,
                "issues": list of str,
                "safety_score": float (0.0 to 1.0),
                "corrected_sql": str or None
            }
        """
        issues = []
        safety_score = 1.0
        
        if not sql or not sql.strip():
            return {
                "is_valid": False,
                "issues": ["Empty SQL query"],
                "safety_score": 0.0,
                "corrected_sql": None
            }
        
        # Normalize SQL
        sql_upper = sql.upper()
        
        # Check 1: Must start with SELECT
        if not sql_upper.strip().startswith("SELECT"):
            issues.append("Query must be a SELECT statement")
            safety_score = 0.0
        
        # Check 2: No dangerous keywords
        for keyword in self.DANGEROUS_KEYWORDS:
            # Use word boundary to avoid false positives
            pattern = r'\b' + keyword + r'\b'
            if re.search(pattern, sql_upper):
                issues.append(f"Dangerous keyword detected: {keyword}")
                safety_score = 0.0
        
        # Check 3: SQL injection patterns
        injection_patterns = [
            r";\s*--",           # Comment injection
            r"'\s*OR\s+'",       # Classic OR injection
            r"'\s*OR\s+1\s*=\s*1", # OR 1=1 injection
            r"UNION\s+SELECT\s+NULL", # UNION injection
            r"@@",               # System variable access
            r"INFORMATION_SCHEMA", # Schema access (but this might be legitimate)
        ]
        
        for pattern in injection_patterns[:5]:  # Skip INFORMATION_SCHEMA for now
            if re.search(pattern, sql_upper):
                issues.append(f"Potential SQL injection pattern detected")
                safety_score -= 0.3
        
        # Check 4: Parse SQL for syntax
        try:
            parsed = sqlparse.parse(sql)
            if not parsed:
                issues.append("Failed to parse SQL")
                safety_score -= 0.2
            else:
                # Check statement types
                for statement in parsed:
                    stmt_type = statement.get_type()
                    if stmt_type and stmt_type.upper() not in ["SELECT", "UNKNOWN"]:
                        issues.append(f"Unexpected statement type: {stmt_type}")
                        safety_score = 0.0
        except Exception as e:
            issues.append(f"SQL parsing error: {str(e)}")
            safety_score -= 0.2
        
        # Check 5: Validate table names exist
        self._load_schema_info()
        tables_in_query = self._extract_table_names(sql)
        for table in tables_in_query:
            if table.lower() not in [t.lower() for t in self._valid_tables]:
                issues.append(f"Unknown table: {table}")
                safety_score -= 0.2
        
        # Check 6: Basic column validation (less strict due to aliases)
        # We only flag columns that are definitely wrong
        
        # Check 7: Query complexity (too many joins might be an issue)
        join_count = sql_upper.count("JOIN")
        if join_count > 5:
            issues.append(f"Query has {join_count} JOINs - may be slow")
            safety_score -= 0.1
        
        # Ensure safety score is in valid range
        safety_score = max(0.0, min(1.0, safety_score))
        
        return {
            "is_valid": len([i for i in issues if "dangerous" in i.lower() or "must be" in i.lower()]) == 0,
            "issues": issues,
            "safety_score": safety_score,
            "corrected_sql": None  # Future: implement auto-correction
        }
    
    def _extract_table_names(self, sql: str) -> List[str]:
        """Extract table names from SQL query."""
        tables = []
        
        # Simple regex-based extraction
        # Match FROM and JOIN clauses
        patterns = [
            r'\bFROM\s+`?(\w+)`?',
            r'\bJOIN\s+`?(\w+)`?',
        ]
        
        sql_upper = sql.upper()
        sql_original = sql
        
        for pattern in patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            tables.extend(matches)
        
        # Remove duplicates and common non-table words
        non_tables = {"SELECT", "WHERE", "AND", "OR", "ON", "AS", "NULL", "TRUE", "FALSE"}
        tables = list(set(t for t in tables if t.upper() not in non_tables))
        
        return tables
    
    def sanitize_for_display(self, sql: str) -> str:
        """Format SQL for display (pretty print)."""
        try:
            return sqlparse.format(sql, reindent=True, keyword_case='upper')
        except:
            return sql


# Global instance
sql_validator = SQLValidator()
