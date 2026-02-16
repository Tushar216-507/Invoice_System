"""
backend/api_schemas.py - Response Format Schemas
Defines consistent response formats for frontend integration
"""

from typing import Dict, List, Optional, Any
from datetime import datetime


class ResponseBuilder:
    """
    Builder class for creating standardized API responses
    """

    @staticmethod
    def needs_entity_clarification(
        conversation_id: str,
        message: str,
        vendor_matches: List[Dict],
        user_matches: List[Dict],
        search_terms: List[str]
    ) -> Dict[str, Any]:
        """
        Build response requesting entity selection from user
        
        Args:
            conversation_id: Conversation ID
            message: Message to display to user
            vendor_matches: List of matching vendors
            user_matches: List of matching users
            search_terms: Original search terms
            
        Returns:
            Response dictionary
        """
        total_matches = len(vendor_matches) + len(user_matches)
        
        return {
            "conversation_id": conversation_id,
            "needs_clarification": True,
            "clarification_type": "entity_selection",
            "state": "awaiting_entity_selection",
            "message": message or f"I found {total_matches} matches for '{', '.join(search_terms)}'. Please select which one you're looking for:",
            "options": {
                "vendors": vendor_matches,
                "users": user_matches,
                "total": total_matches
            },
            "metadata": {
                "search_terms": search_terms,
                "timestamp": datetime.now().isoformat()
            }
        }

    @staticmethod
    def needs_date_range(
        conversation_id: str,
        selected_entity: Dict,
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build response requesting date range selection
        
        Args:
            conversation_id: Conversation ID
            selected_entity: Entity user selected
            message: Optional custom message
            
        Returns:
            Response dictionary
        """
        default_message = f"Please select a date range for {selected_entity['name']}:"
        
        return {
            "conversation_id": conversation_id,
            "needs_clarification": True,
            "clarification_type": "date_range",
            "state": "awaiting_date_range",
            "message": message or default_message,
            "selected_entity": {
                "type": selected_entity["type"],
                "id": selected_entity["id"],
                "name": selected_entity["name"],
                "shortform": selected_entity.get("shortform", "")
            },
            "date_options": {
                "quick_picks": [
                    {
                        "label": "This Month",
                        "value": "this_month",
                        "description": "Current calendar month"
                    },
                    {
                        "label": "Last Month",
                        "value": "last_month",
                        "description": "Previous calendar month"
                    },
                    {
                        "label": "This Quarter",
                        "value": "this_quarter",
                        "description": "Current financial quarter"
                    },
                    {
                        "label": "Current Financial Year",
                        "value": "current_fy",
                        "description": "April 1st to March 31st (current)"
                    },
                    {
                        "label": "Previous Financial Year",
                        "value": "previous_fy",
                        "description": "April 1st to March 31st (previous)"
                    },
                    {
                        "label": "Custom Range",
                        "value": "custom",
                        "description": "Select your own date range"
                    }
                ],
                "custom_range_enabled": True
            },
            "metadata": {
                "timestamp": datetime.now().isoformat()
            }
        }

    @staticmethod
    def query_success(
        conversation_id: str,
        response_text: str,
        data: List[Dict],
        sql: str,
        selected_entity: Optional[Dict] = None,
        date_range: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Build successful query response
        
        Args:
            conversation_id: Conversation ID
            response_text: Natural language response
            data: Query results
            sql: Executed SQL
            selected_entity: Entity that was queried
            date_range: Date range used
            
        Returns:
            Response dictionary
        """
        return {
            "conversation_id": conversation_id,
            "needs_clarification": False,
            "state": "completed",
            "response": response_text,
            "data": data,
            "data_count": len(data),
            "query_info": {
                "sql": sql,
                "selected_entity": selected_entity,
                "date_range": date_range,
                "executed_at": datetime.now().isoformat()
            },
            "error": False
        }

    @staticmethod
    def error_response(
        conversation_id: str,
        error_message: str,
        error_type: Optional[str] = None,
        details: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Build error response
        
        Args:
            conversation_id: Conversation ID
            error_message: Error message for user
            error_type: Type of error (optional)
            details: Additional error details (optional)
            
        Returns:
            Response dictionary
        """
        return {
            "conversation_id": conversation_id,
            "needs_clarification": False,
            "state": "error",
            "response": error_message,
            "data": [],
            "error": True,
            "error_details": {
                "type": error_type or "unknown",
                "message": error_message,
                "details": details or {},
                "timestamp": datetime.now().isoformat()
            }
        }

    @staticmethod
    def no_matches_found(
        conversation_id: str,
        search_terms: List[str],
        suggestions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Build response when no entities match search
        
        Args:
            conversation_id: Conversation ID
            search_terms: Terms that were searched
            suggestions: Optional suggestions for user
            
        Returns:
            Response dictionary
        """
        message = f"I couldn't find any vendors or users matching '{', '.join(search_terms)}'.\n\n"
        
        if suggestions:
            message += "Did you mean:\n" + "\n".join(f"• {s}" for s in suggestions)
        else:
            message += "Please try:\n"
            message += "• Checking the spelling\n"
            message += "• Using the full name instead of abbreviation\n"
            message += "• Using a different search term"
        
        return {
            "conversation_id": conversation_id,
            "needs_clarification": False,
            "state": "no_results",
            "response": message,
            "data": [],
            "search_info": {
                "search_terms": search_terms,
                "suggestions": suggestions or []
            },
            "error": False
        }

    @staticmethod
    def ambiguous_query(
        conversation_id: str,
        message: str,
        clarification_needed: str
    ) -> Dict[str, Any]:
        """
        Build response for ambiguous queries
        
        Args:
            conversation_id: Conversation ID
            message: Message to user
            clarification_needed: What needs to be clarified
            
        Returns:
            Response dictionary
        """
        return {
            "conversation_id": conversation_id,
            "needs_clarification": True,
            "clarification_type": "general",
            "state": "awaiting_clarification",
            "response": message,
            "clarification_needed": clarification_needed,
            "metadata": {
                "timestamp": datetime.now().isoformat()
            }
        }


class DateRangeHelper:
    """
    Helper class for date range calculations
    """

    @staticmethod
    def get_date_range(quick_pick: str) -> Optional[Dict[str, str]]:
        """
        Convert quick pick value to actual date range
        
        Args:
            quick_pick: Quick pick option (this_month, last_month, etc.)
            
        Returns:
            Dictionary with 'from' and 'to' dates or None
        """
        from datetime import date, timedelta
        from dateutil.relativedelta import relativedelta
        
        today = date.today()
        
        if quick_pick == "this_month":
            first_day = today.replace(day=1)
            # Get last day of current month
            next_month = first_day + relativedelta(months=1)
            last_day = next_month - timedelta(days=1)
            return {
                "from": first_day.strftime("%Y-%m-%d"),
                "to": last_day.strftime("%Y-%m-%d")
            }
        
        elif quick_pick == "last_month":
            first_day = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
            last_day = today.replace(day=1) - timedelta(days=1)
            return {
                "from": first_day.strftime("%Y-%m-%d"),
                "to": last_day.strftime("%Y-%m-%d")
            }
        
        elif quick_pick == "this_quarter":
            # Get current quarter
            quarter = (today.month - 1) // 3 + 1
            first_month = (quarter - 1) * 3 + 1
            first_day = date(today.year, first_month, 1)
            # Last day of quarter
            last_month = first_month + 2
            if last_month <= 12:
                last_day = date(today.year, last_month, 1) + relativedelta(months=1) - timedelta(days=1)
            else:
                last_day = date(today.year, 12, 31)
            return {
                "from": first_day.strftime("%Y-%m-%d"),
                "to": last_day.strftime("%Y-%m-%d")
            }
        
        elif quick_pick == "current_fy":
            # Indian FY: April 1 to March 31
            if today.month >= 4:
                fy_start = date(today.year, 4, 1)
                fy_end = date(today.year + 1, 3, 31)
            else:
                fy_start = date(today.year - 1, 4, 1)
                fy_end = date(today.year, 3, 31)
            return {
                "from": fy_start.strftime("%Y-%m-%d"),
                "to": fy_end.strftime("%Y-%m-%d")
            }
        
        elif quick_pick == "previous_fy":
            # Previous Indian FY
            if today.month >= 4:
                fy_start = date(today.year - 1, 4, 1)
                fy_end = date(today.year, 3, 31)
            else:
                fy_start = date(today.year - 2, 4, 1)
                fy_end = date(today.year - 1, 3, 31)
            return {
                "from": fy_start.strftime("%Y-%m-%d"),
                "to": fy_end.strftime("%Y-%m-%d")
            }
        
        return None

    @staticmethod
    def validate_date_range(from_date: str, to_date: str) -> tuple[bool, Optional[str]]:
        """
        Validate date range
        
        Args:
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        from datetime import datetime
        
        try:
            start = datetime.strptime(from_date, "%Y-%m-%d")
            end = datetime.strptime(to_date, "%Y-%m-%d")
            
            if start > end:
                return False, "Start date cannot be after end date"
            
            # Check if date range is reasonable (not more than 10 years)
            if (end - start).days > 3650:
                return False, "Date range cannot exceed 10 years"
            
            return True, None
            
        except ValueError:
            return False, "Invalid date format. Please use YYYY-MM-DD"


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example: Entity clarification response
    response = ResponseBuilder.needs_entity_clarification(
        conversation_id="abc-123",
        message="I found 3 matches",
        vendor_matches=[
            {
                "type": "vendor",
                "id": 123,
                "name": "Nimayate Creative Solutions",
                "shortform": "NCS",
                "preview": "5 invoices found"
            }
        ],
        user_matches=[
            {
                "type": "user",
                "id": 789,
                "name": "Nicolas Smith",
                "email": "nsmith@company.com",
                "preview": "Created 2 invoices"
            }
        ],
        search_terms=["NCS"]
    )
    
    print("Entity Clarification Response:")
    import json
    print(json.dumps(response, indent=2))
