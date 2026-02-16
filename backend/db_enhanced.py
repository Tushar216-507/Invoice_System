"""
backend/db_enhanced.py - Enhanced Database Manager
Additional methods for fuzzy search and entity matching
ADD THESE METHODS to your existing db.py
"""

import logging
from typing import List, Dict, Optional
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


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
