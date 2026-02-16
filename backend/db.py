"""
backend/db.py - Database connection and query execution
Handles MySQL database operations for the chatbot
"""

import logging
import mysql.connector
from mysql.connector import Error
from typing import List, Dict, Optional
import os


import logging
from typing import List, Dict, Optional
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages MySQL database connections and queries"""

    def __init__(self):
        """Initialize database connection"""
        self.connection = None
        self.host = os.getenv("DB_HOST", "localhost")
        self.port = int(os.getenv("DB_PORT", 3306))
        self.user = os.getenv("DB_USER", "root")
        self.password = os.getenv("DB_PASSWORD", "")
        self.database = os.getenv("DB_NAME", "invoice_uat_db")

        logger.info(
            f"📌 Database config: {self.user}@{self.host}:{self.port}/{self.database}"
        )

        self.connect()

    # ====================================================================
    # CONNECTION MANAGEMENT
    # ====================================================================

    def connect(self) -> bool:
        """
        Establish connection to MySQL database.
        """
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                autocommit=True,
                connection_timeout=10,
            )

            if self.connection.is_connected():
                db_info = self.connection.get_server_info()
                logger.info(f"✅ Connected to MySQL Server version {db_info}")
                logger.info(f"✅ Database: {self.database}")
                return True

        except Error as e:
            logger.error(f"❌ Connection error: {str(e)}")
            return False

    def disconnect(self) -> bool:
        """
        Close database connection.
        """
        try:
            if self.connection and self.connection.is_connected():
                self.connection.close()
                logger.info("✅ Database connection closed")
                return True
        except Error as e:
            logger.error(f"❌ Disconnection error: {str(e)}")

        return False

    def reconnect(self) -> bool:
        """Reconnect to database if connection lost."""
        try:
            if not self.connection or not self.connection.is_connected():
                logger.warning("⚠️  Reconnecting to database...")
                return self.connect()
            return True
        except Exception as e:
            logger.error(f"❌ Reconnection failed: {str(e)}")
            return False

    # ====================================================================
    # QUERY EXECUTION
    # ====================================================================

    def execute_query(
        self, sql: str, params: Optional[tuple] = None
    ) -> List[Dict]:
        """
        Execute SELECT query and return results.
        """
        try:
            if not self.reconnect():
                raise Exception("Database not connected")

            logger.info(f"🔍 Executing query: {sql[:200]}...")

            cursor = self.connection.cursor(dictionary=True)

            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)

            results = cursor.fetchall()
            cursor.close()

            logger.info(f"✅ Query returned {len(results)} rows")
            return results

        except Error as e:
            logger.error(f"❌ Query execution error: {str(e)}")
            logger.error(f"   SQL: {sql}")
            raise Exception(f"Query failed: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Unexpected error: {str(e)}")
            raise Exception(f"Query execution failed: {str(e)}")

    def execute_update(self, sql: str, params: Optional[tuple] = None) -> int:
        """
        Execute INSERT, UPDATE, DELETE query.
        """
        try:
            if not self.reconnect():
                raise Exception("Database not connected")

            logger.info(f"✏️  Executing update: {sql[:200]}...")

            cursor = self.connection.cursor()

            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)

            affected_rows = cursor.rowcount
            cursor.close()

            logger.info(f"✅ Update affected {affected_rows} rows")
            return affected_rows

        except Error as e:
            logger.error(f"❌ Update error: {str(e)}")
            raise Exception(f"Update failed: {str(e)}")

    # ====================================================================
    # SCHEMA & METADATA
    # ====================================================================

    def get_schema(self) -> str:
        """
        Get database schema as formatted string.
        """
        try:
            if not self.reconnect():
                raise Exception("Database not connected")

            logger.info("📋 Fetching database schema...")

            cursor = self.connection.cursor()

            cursor.execute(
                f"SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                f"WHERE TABLE_SCHEMA = '{self.database}'"
            )
            tables = cursor.fetchall()

            schema_text = f"Database: {self.database}\n\n"

            for (table_name,) in tables:
                schema_text += f"TABLE: {table_name}\n"
                schema_text += "-" * 50 + "\n"

                cursor.execute(
                    f"""
                    SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = '{self.database}'
                      AND TABLE_NAME = '{table_name}'
                    """
                )
                columns = cursor.fetchall()

                for col_name, col_type, nullable, col_key in columns:
                    nullable_str = (
                        "NULL" if nullable == "YES" else "NOT NULL"
                    )
                    key_str = f"[{col_key}]" if col_key else ""
                    schema_text += (
                        f"  - {col_name} ({col_type}) "
                        f"{nullable_str} {key_str}\n"
                    )

                schema_text += "\n"

            cursor.close()

            logger.info("✅ Schema retrieved")
            return schema_text

        except Error as e:
            logger.error(f"❌ Schema retrieval error: {str(e)}")
            return f"Error getting schema: {str(e)}"

    def get_tables(self) -> List[str]:
        """
        Get list of all tables in database.
        """
        try:
            if not self.reconnect():
                raise Exception("Database not connected")

            cursor = self.connection.cursor()
            cursor.execute(
                f"SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                f"WHERE TABLE_SCHEMA = '{self.database}'"
            )
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()

            logger.info(f"✅ Found {len(tables)} tables")
            return tables

        except Error as e:
            logger.error(f"❌ Error getting tables: {str(e)}")
            return []

    def get_table_info(self, table_name: str) -> Dict:
        """
        Get detailed information about a table.
        """
        try:
            if not self.reconnect():
                raise Exception("Database not connected")

            cursor = self.connection.cursor(dictionary=True)

            cursor.execute(
                f"""
                SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY, EXTRA
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = '{self.database}'
                  AND TABLE_NAME = '{table_name}'
                """
            )
            columns = cursor.fetchall()

            cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
            row_count = cursor.fetchone()["count"]

            cursor.close()

            return {
                "table_name": table_name,
                "columns": columns,
                "row_count": row_count,
            }

        except Error as e:
            logger.error(f"❌ Error getting table info: {str(e)}")
            return {}

    # ====================================================================
    # UTILITY METHODS
    # ====================================================================

    def test_connection(self) -> bool:
        """
        Test if database connection is working.
        """
        try:
            if not self.connection:
                return False

            if not self.connection.is_connected():
                logger.warning(
                    "⚠️  Connection lost, attempting to reconnect..."
                )
                return self.reconnect()

            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()

            logger.info("✅ Connection test successful")
            return True

        except Error as e:
            logger.error(f"❌ Connection test failed: {str(e)}")
            return False

    def escape_string(self, value: str) -> str:
        """
        Escape string for SQL query.
        """
        try:
            cursor = self.connection.cursor()
            escaped = cursor.connection.escape_string(value)
            cursor.close()
            return escaped
        except Exception as e:
            logger.error(f"❌ Error escaping string: {str(e)}")
            return value

    def get_last_insert_id(self) -> int:
        """
        Get last inserted row ID.
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT LAST_INSERT_ID() as id")
            result = cursor.fetchone()
            cursor.close()
            return result[0] if result else 0
        except Error as e:
            logger.error(f"❌ Error getting last insert ID: {str(e)}")
            return 0

    """
backend/db_enhanced.py - Enhanced Database Manager
Additional methods for fuzzy search and entity matching
ADD THESE METHODS to your existing db.py
"""

    # ============================================================================
    # ADD THESE METHODS TO YOUR EXISTING DatabaseManager CLASS
    # ============================================================================

    def fuzzy_search_entities(self, search_term: str, threshold: float = 0.6) -> Dict[str, List[Dict]]:
        """
        Fuzzy search across users and vendors tables
        
        Args:
            search_term: Term to search for
            threshold: Minimum similarity score (0.0 to 1.0)
            
        Returns:
            Dictionary with 'vendors' and 'users' lists
        """
        try:
            if not self.reconnect():
                raise Exception("Database not connected")
            
            logger.info(f"🔍 Fuzzy searching for: {search_term}")
            
            # Search vendors
            vendor_sql = """
            SELECT 
                id,
                vendor_name,
                shortforms_of_vendors,
                vendor_status,
                department,
                PAN,
                GSTIN
            FROM vendors
            WHERE vendor_status = 'Active'
            AND (
                LOWER(vendor_name) LIKE LOWER(%s)
                OR LOWER(shortforms_of_vendors) LIKE LOWER(%s)
            )
            ORDER BY vendor_name
            """
            
            like_pattern = f"%{search_term}%"
            vendors = self.execute_query(vendor_sql, (like_pattern, like_pattern))
            
            # Search users
            user_sql = """
            SELECT 
                id,
                name,
                email,
                role,
                department,
                is_active
            FROM users
            WHERE is_active = 1
            AND (
                LOWER(name) LIKE LOWER(%s)
                OR LOWER(email) LIKE LOWER(%s)
            )
            ORDER BY name
            """
            
            users = self.execute_query(user_sql, (like_pattern, like_pattern))
            
            logger.info(f"✅ Found {len(vendors)} vendors and {len(users)} users")
            
            return {
                "vendors": vendors,
                "users": users,
                "total": len(vendors) + len(users)
            }
            
        except Exception as e:
            logger.error(f"❌ Fuzzy search failed: {str(e)}")
            return {"vendors": [], "users": [], "total": 0}


    def get_entity_invoice_count(self, entity_type: str, entity_name: str) -> int:
        """
        Get count of invoices for an entity
        
        Args:
            entity_type: 'vendor' or 'user'
            entity_name: Name of the entity
            
        Returns:
            Count of invoices
        """
        try:
            if not self.reconnect():
                raise Exception("Database not connected")
            
            if entity_type == 'vendor':
                sql = """
                SELECT COUNT(*) as count
                FROM invoices
                WHERE vendor = %s
                """
            elif entity_type == 'user':
                sql = """
                SELECT COUNT(*) as count
                FROM invoices
                WHERE created_by = %s
                OR approved_by = %s
                OR reviewed_by = %s
                """
                result = self.execute_query(sql, (entity_name, entity_name, entity_name))
                return result[0]['count'] if result else 0
            else:
                return 0
            
            result = self.execute_query(sql, (entity_name,))
            return result[0]['count'] if result else 0
            
        except Exception as e:
            logger.error(f"❌ Get invoice count failed: {str(e)}")
            return 0


    def get_vendor_by_id(self, vendor_id: int) -> Optional[Dict]:
        """
        Get vendor by ID
        
        Args:
            vendor_id: Vendor ID
            
        Returns:
            Vendor dictionary or None
        """
        try:
            sql = """
            SELECT 
                id,
                vendor_name,
                shortforms_of_vendors,
                vendor_status,
                department,
                vendor_address,
                PAN,
                GSTIN,
                POC,
                POC_number,
                POC_email
            FROM vendors
            WHERE id = %s
            """
            
            result = self.execute_query(sql, (vendor_id,))
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"❌ Get vendor failed: {str(e)}")
            return None


    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """
        Get user by ID
        
        Args:
            user_id: User ID
            
        Returns:
            User dictionary or None
        """
        try:
            sql = """
            SELECT 
                id,
                name,
                email,
                role,
                department,
                is_active,
                created_at
            FROM users
            WHERE id = %s
            """
            
            result = self.execute_query(sql, (user_id,))
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"❌ Get user failed: {str(e)}")
            return None


    def execute_query_with_logging(self, sql: str, params: Optional[tuple] = None) -> List[Dict]:
        """
        Execute query with detailed performance logging
        
        Args:
            sql: SQL query
            params: Query parameters
            
        Returns:
            Query results
        """
        import time
        
        try:
            if not self.reconnect():
                raise Exception("Database not connected")
            
            start_time = time.time()
            
            logger.info(f"🔍 Executing query: {sql[:200]}...")
            
            cursor = self.connection.cursor(dictionary=True)
            
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            
            results = cursor.fetchall()
            cursor.close()
            
            execution_time = time.time() - start_time
            
            logger.info(f"✅ Query returned {len(results)} rows in {execution_time:.2f}s")
            
            # Warn on slow queries
            if execution_time > 2.0:
                logger.warning(f"⚠️ Slow query detected: {execution_time:.2f}s")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Query execution error: {str(e)}")
            logger.error(f"   SQL: {sql}")
            raise Exception(f"Query failed: {str(e)}")

    # ====================================================================
    # CONTEXT MANAGER & CLEANUP
    # ====================================================================

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def close(self):
        """Close database connection."""
        self.disconnect()


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

try:
    db_instance = DatabaseManager()
    logger.info("✅ Database instance created")
except Exception as e:
    logger.error(f"❌ Failed to create database instance: {str(e)}")
    db_instance = None
