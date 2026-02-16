"""
Database connection and query execution module.
Handles MySQL connections, schema introspection, and safe query execution.
"""
import mysql.connector
from mysql.connector import pooling
from typing import Dict, List, Any, Optional, Tuple
from contextlib import contextmanager
import logging

from .config import config

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and query execution."""
    
    def __init__(self):
        self._pool = None
        self._schema_cache: Optional[Dict] = None
    
    def _get_pool(self) -> pooling.MySQLConnectionPool:
        """Get or create connection pool."""
        if self._pool is None:
            self._pool = pooling.MySQLConnectionPool(
                pool_name="chatbot_pool",
                pool_size=5,
                pool_reset_session=True,
                host=config.DB_HOST,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                database=config.DB_NAME,
                port=config.DB_PORT,
                connect_timeout=10,
                autocommit=True
            )
        return self._pool
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool."""
        conn = None
        try:
            conn = self._get_pool().get_connection()
            yield conn
        finally:
            if conn:
                conn.close()
    
    def execute_query(self, query: str, params: tuple = None) -> Tuple[List[Dict], List[str]]:
        """
        Execute a SELECT query and return results as list of dicts.
        Returns: (results, column_names)
        """
        with self.get_connection() as conn:
            # Use buffered cursor to avoid "Unread result found" errors
            cursor = conn.cursor(dictionary=True, buffered=True)
            try:
                cursor.execute(query, params)
                # Fetch ALL results to avoid unread result issues
                all_results = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                
                # Log the actual count for debugging
                logger.info(f"Query returned {len(all_results)} rows")
                
                return all_results, columns
            except mysql.connector.Error as e:
                logger.error(f"Query execution error: {e}")
                raise
            finally:
                # Consume any remaining results to clear the cursor
                try:
                    while cursor.nextset():
                        pass
                except:
                    pass
                cursor.close()
    
    def get_schema(self, force_refresh: bool = False) -> Dict:
        """
        Get the complete database schema with detailed metadata.
        Cached for performance.
        """
        if self._schema_cache and not force_refresh:
            return self._schema_cache
        
        schema = {}
        
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Get all tables
            cursor.execute("SHOW TABLES")
            tables = [list(row.values())[0] for row in cursor.fetchall()]
            
            for table in tables:
                # Get column info
                cursor.execute(f"DESCRIBE `{table}`")
                columns = cursor.fetchall()
                
                # Get sample values for enum/categorical columns
                column_info = []
                for col in columns:
                    col_data = {
                        "name": col["Field"],
                        "type": col["Type"],
                        "nullable": col["Null"] == "YES",
                        "key": col["Key"],
                        "default": col["Default"],
                        "extra": col["Extra"]
                    }
                    
                    # Get sample values for enum types
                    if "enum" in col["Type"].lower():
                        # Extract enum values from type definition
                        enum_str = col["Type"]
                        values = enum_str.replace("enum(", "").replace(")", "").replace("'", "").split(",")
                        col_data["enum_values"] = values
                    
                    # Get sample values for varchar columns that might be categorical
                    elif "varchar" in col["Type"].lower() and col["Field"] in ["department", "vendor_status", "role"]:
                        try:
                            cursor.execute(f"SELECT DISTINCT `{col['Field']}` FROM `{table}` LIMIT 10")
                            samples = [row[col["Field"]] for row in cursor.fetchall() if row[col["Field"]]]
                            col_data["sample_values"] = samples
                        except:
                            pass
                    
                    column_info.append(col_data)
                
                # Get row count
                cursor.execute(f"SELECT COUNT(*) as cnt FROM `{table}`")
                row_count = cursor.fetchone()["cnt"]
                
                schema[table] = {
                    "columns": column_info,
                    "row_count": row_count
                }
            
            cursor.close()
        
        self._schema_cache = schema
        return schema
    
    def get_table_relationships(self) -> Dict[str, List[str]]:
        """
        Infer table relationships based on column naming patterns.
        """
        relationships = {
            "invoices": {
                "vendor": "vendors.vendor_name",
                "created_by": "users.email",
                "approved_by": "users.email",
                "reviewed_by": "users.email",
                "po_number": "purchase_orders.po_number"
            },
            "purchase_orders": {
                "vendor_id": "vendors.id",
                "created_by": "users.id",
                "approved_by": "users.id",
                "reviewed_by": "users.id"
            },
            "purchase_order_items": {
                "po_id": "purchase_orders.id"
            },
            "activity_log": {
                "user_email": "users.email"
            }
        }
        return relationships
    
    def health_check(self) -> bool:
        """Check if database connection is healthy."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# Global database manager instance
db = DatabaseManager()
