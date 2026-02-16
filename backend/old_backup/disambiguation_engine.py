"""
backend/disambiguation_engine.py - Entity Disambiguation System
Handles fuzzy matching of users and vendors to resolve ambiguous queries
"""

import logging
from typing import List, Dict, Optional
from difflib import SequenceMatcher
import re

logger = logging.getLogger(__name__)


class DisambiguationEngine:
    """
    Handles entity disambiguation by searching both users and vendors
    and presenting matches for user confirmation
    """

    def __init__(self, db_manager):
        """
        Initialize disambiguation engine
        
        Args:
            db_manager: DatabaseManager instance
        """
        self.db = db_manager
        logger.info("✅ DisambiguationEngine initialized")

    # ====================================================================
    # ENTITY EXTRACTION
    # ====================================================================

    def extract_search_terms(self, message: str) -> List[str]:
        """
        Extract potential entity names from user message
        
        Args:
            message: User's natural language query
            
        Returns:
            List of potential search terms
        """
        # Remove common query words
        stop_words = {
            'show', 'me', 'get', 'find', 'list', 'give', 'tell',
            'invoices', 'invoice', 'of', 'for', 'from', 'by',
            'created', 'approved', 'reviewed', 'the', 'all',
            'pending', 'cleared', 'total', 'amount', 'details'
        }
        
        # Extract words
        words = re.findall(r'\b[A-Za-z0-9]+\b', message)
        
        # Filter out stop words
        search_terms = [w for w in words if w.lower() not in stop_words and len(w) > 1]
        
        # Also try to capture quoted strings
        quoted = re.findall(r'"([^"]+)"', message)
        search_terms.extend(quoted)
        
        # Try to capture multi-word names (capitalized sequences)
        capitalized = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', message)
        search_terms.extend(capitalized)
        
        logger.info(f"🔍 Extracted search terms: {search_terms}")
        return search_terms

    # ====================================================================
    # FUZZY MATCHING
    # ====================================================================

    def _similarity_score(self, str1: str, str2: str) -> float:
        """
        Calculate similarity score between two strings
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

    def _matches_search_term(self, entity_name: str, search_term: str, threshold: float = 0.6) -> bool:
        """
        Check if entity name matches search term with fuzzy matching
        
        Args:
            entity_name: Name of the entity (user or vendor)
            search_term: Search term from user query
            threshold: Minimum similarity threshold (0.0 to 1.0)
            
        Returns:
            True if match found
        """
        entity_lower = entity_name.lower()
        search_lower = search_term.lower()
        
        # Exact substring match
        if search_lower in entity_lower:
            return True
        
        # Fuzzy match
        if self._similarity_score(entity_name, search_term) >= threshold:
            return True
        
        # Check individual words
        entity_words = entity_lower.split()
        for word in entity_words:
            if self._similarity_score(word, search_lower) >= threshold:
                return True
        
        return False

    # ====================================================================
    # VENDOR SEARCH
    # ====================================================================

    def search_vendors(self, search_terms: List[str]) -> List[Dict]:
        """
        Search vendors table with fuzzy matching
        
        Args:
            search_terms: List of search terms
            
        Returns:
            List of matching vendor dictionaries with metadata
        """
        try:
            # Get all active vendors
            sql = """
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
            ORDER BY vendor_name
            """
            
            vendors = self.db.execute_query(sql)
            
            matches = []
            for vendor in vendors:
                vendor_name = vendor['vendor_name']
                shortform = vendor.get('shortforms_of_vendors', '')
                
                # Check if any search term matches
                for search_term in search_terms:
                    if self._matches_search_term(vendor_name, search_term):
                        matches.append(vendor)
                        break
                    elif shortform and self._matches_search_term(shortform, search_term):
                        matches.append(vendor)
                        break
            
            # Get invoice counts for each vendor
            for match in matches:
                count_sql = """
                SELECT COUNT(*) as count
                FROM invoices
                WHERE vendor = %s
                """
                result = self.db.execute_query(count_sql, (match['vendor_name'],))
                match['invoice_count'] = result[0]['count'] if result else 0
            
            logger.info(f"✅ Found {len(matches)} vendor matches")
            return matches
            
        except Exception as e:
            logger.error(f"❌ Vendor search failed: {str(e)}")
            return []

    # ====================================================================
    # USER SEARCH
    # ====================================================================

    def search_users(self, search_terms: List[str]) -> List[Dict]:
        """
        Search users table with fuzzy matching
        
        Args:
            search_terms: List of search terms
            
        Returns:
            List of matching user dictionaries with metadata
        """
        try:
            # Get all active users
            sql = """
            SELECT 
                id,
                name,
                email,
                role,
                department,
                is_active
            FROM users
            WHERE is_active = 1
            ORDER BY name
            """
            
            users = self.db.execute_query(sql)
            
            matches = []
            for user in users:
                user_name = user['name']
                user_email = user.get('email', '')
                
                # Check if any search term matches
                for search_term in search_terms:
                    if self._matches_search_term(user_name, search_term):
                        matches.append(user)
                        break
                    elif user_email and search_term.lower() in user_email.lower():
                        matches.append(user)
                        break
            
            # Get invoice counts for each user
            for match in matches:
                # Count invoices created by user
                count_sql = """
                SELECT COUNT(*) as count
                FROM invoices
                WHERE created_by = %s
                """
                result = self.db.execute_query(count_sql, (match['name'],))
                match['created_invoice_count'] = result[0]['count'] if result else 0
                
                # Count invoices approved by user
                approved_sql = """
                SELECT COUNT(*) as count
                FROM invoices
                WHERE approved_by = %s
                """
                result = self.db.execute_query(approved_sql, (match['name'],))
                match['approved_invoice_count'] = result[0]['count'] if result else 0
            
            logger.info(f"✅ Found {len(matches)} user matches")
            return matches
            
        except Exception as e:
            logger.error(f"❌ User search failed: {str(e)}")
            return []

    # ====================================================================
    # COMBINED SEARCH
    # ====================================================================

    def search_all_entities(self, message: str) -> Dict[str, any]:
        """
        Search both users and vendors for potential matches
        
        Args:
            message: User's natural language query
            
        Returns:
            Dictionary containing vendor and user matches with metadata
        """
        logger.info(f"🔍 Searching all entities for: {message}")
        
        # Extract search terms
        search_terms = self.extract_search_terms(message)
        
        if not search_terms:
            logger.warning("⚠️ No search terms extracted from message")
            return {
                "needs_clarification": False,
                "vendor_matches": [],
                "user_matches": [],
                "total_matches": 0
            }
        
        # Search both tables
        vendor_matches = self.search_vendors(search_terms)
        user_matches = self.search_users(search_terms)
        
        total_matches = len(vendor_matches) + len(user_matches)
        
        # Format vendor matches
        formatted_vendors = []
        for vendor in vendor_matches:
            formatted_vendors.append({
                "type": "vendor",
                "id": vendor['id'],
                "name": vendor['vendor_name'],
                "shortform": vendor.get('shortforms_of_vendors', ''),
                "department": vendor.get('department', ''),
                "preview": f"{vendor['invoice_count']} invoices found",
                "invoice_count": vendor['invoice_count'],
                "metadata": {
                    "pan": vendor.get('PAN', ''),
                    "gstin": vendor.get('GSTIN', '')
                }
            })
        
        # Format user matches
        formatted_users = []
        for user in user_matches:
            formatted_users.append({
                "type": "user",
                "id": user['id'],
                "name": user['name'],
                "email": user.get('email', ''),
                "role": user.get('role', ''),
                "department": user.get('department', ''),
                "preview": f"Created {user['created_invoice_count']} invoices, Approved {user['approved_invoice_count']}",
                "created_count": user['created_invoice_count'],
                "approved_count": user['approved_invoice_count']
            })
        
        logger.info(f"📊 Total matches: {total_matches} (Vendors: {len(vendor_matches)}, Users: {len(user_matches)})")
        
        return {
            "needs_clarification": total_matches > 1 or total_matches == 0,
            "vendor_matches": formatted_vendors,
            "user_matches": formatted_users,
            "total_matches": total_matches,
            "search_terms": search_terms
        }

    # ====================================================================
    # ENTITY RETRIEVAL
    # ====================================================================

    def get_entity_by_id(self, entity_type: str, entity_id: int) -> Optional[Dict]:
        """
        Get full entity details by type and ID
        
        Args:
            entity_type: "vendor" or "user"
            entity_id: Entity ID
            
        Returns:
            Entity dictionary or None if not found
        """
        try:
            if entity_type == "vendor":
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
                result = self.db.execute_query(sql, (entity_id,))
                if result:
                    entity = result[0]
                    return {
                        "type": "vendor",
                        "id": entity['id'],
                        "name": entity['vendor_name'],
                        "shortform": entity.get('shortforms_of_vendors', ''),
                        "department": entity.get('department', ''),
                        "full_data": entity
                    }
            
            elif entity_type == "user":
                sql = """
                SELECT 
                    id,
                    name,
                    email,
                    role,
                    department,
                    is_active
                FROM users
                WHERE id = %s
                """
                result = self.db.execute_query(sql, (entity_id,))
                if result:
                    entity = result[0]
                    return {
                        "type": "user",
                        "id": entity['id'],
                        "name": entity['name'],
                        "email": entity.get('email', ''),
                        "role": entity.get('role', ''),
                        "department": entity.get('department', ''),
                        "full_data": entity
                    }
            
            logger.warning(f"⚠️ Entity not found: {entity_type} ID {entity_id}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Get entity failed: {str(e)}")
            return None


# ============================================================================
# GLOBAL INSTANCE (will be created in agent_v2.py)
# ============================================================================
