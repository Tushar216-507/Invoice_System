"""
AI Client implementations - Enhanced with vendor matching and conversation context
"""

import logging
from typing import List, Dict,Optional
import os
from groq import Groq
from openai import OpenAI
import json
import re
from decimal import Decimal
from datetime import datetime, date

logger = logging.getLogger(__name__)

# ============================================================================
# For Financial Year Calculation
# ============================================================================
class FinancialYearHelper:
    """Helper class to calculate Indian financial year dates"""
    
    @staticmethod
    def get_current_fy_dates() -> tuple:
        """
        Returns (fy_start, fy_end) for current financial year
        Indian FY: April 1 to March 31
        """
        today = date.today()
        
        if today.month >= 4:  # April to December
            fy_start = date(today.year, 4, 1)
            fy_end = date(today.year + 1, 3, 31)
        else:  # January to March
            fy_start = date(today.year - 1, 4, 1)
            fy_end = date(today.year, 3, 31)
        
        return fy_start, fy_end
    
    @staticmethod
    def get_previous_fy_dates() -> tuple:
        """Returns (fy_start, fy_end) for previous financial year"""
        today = date.today()
        
        if today.month >= 4:
            fy_start = date(today.year - 1, 4, 1)
            fy_end = date(today.year, 3, 31)
        else:
            fy_start = date(today.year - 2, 4, 1)
            fy_end = date(today.year - 1, 3, 31)
        
        return fy_start, fy_end
    
    @staticmethod
    def get_fy_filter(message: str) -> str:
        """
        Generate SQL date filter based on message content
        Returns WHERE clause snippet for financial year filtering
        """
        message_lower = message.lower()
        
        # ✅ CRITICAL: Don't apply FY filter to user-centric queries
        is_user_query = any(phrase in message_lower for phrase in [
            'user', 'created by', 'approved by', 'reviewed by',
            'who created', 'who approved', 'who reviewed',
            'how many invoices did', 'invoices by',
            'user activity', 'user report', 'user performance',
            'users who', 'list users', 'which user',
            'processed by', 'submitted by'
        ])
        
        if is_user_query:
            logger.info("📅 User query detected - skipping automatic FY filter")
            return ""
        
        # Check if user mentioned specific dates/periods
        has_date_mention = any(word in message_lower for word in [
            'last month', 'this month', 'last week', 'yesterday',
            'last year', 'this year', '2024', '2025', '2026',
            'january', 'february', 'march', 'april', 'may', 'june',
            'july', 'august', 'september', 'october', 'november', 'december',
            'days ago', 'weeks ago', 'months ago'
        ])

        is_previous_fy = any(phrase in message_lower for phrase in [
            'last financial year',
            'last fy', 
            'previous financial year',
            'previous fy',
            'from last financial year',
            'from previous financial year',
            'in last financial year',
            'in previous financial year'
        ])
        
        if is_previous_fy:
            fy_start, fy_end = FinancialYearHelper.get_previous_fy_dates()
            logger.info(f"📅 Previous FY filter: {fy_start} to {fy_end}")   
            return f"AND i.invoice_date >= '{fy_start}' AND i.invoice_date <= '{fy_end}'"
        
        if has_date_mention:
            logger.info("📅 Date mentioned in message, skipping FY filter")
            return ""

        # ✅ Only apply current FY filter for general invoice queries
        fy_start, fy_end = FinancialYearHelper.get_current_fy_dates()
        logger.info(f"📅 Current FY filter: {fy_start} to {fy_end}")
        
        # Return SQL filter snippet
        return f"AND i.invoice_date >= '{fy_start}' AND i.invoice_date <= '{fy_end}'"

# ============================================================================
# INVOICE DB SCHEMA CONTEXT
# ============================================================================

INVOICE_DB_SCHEMA_TEXT = """
DATABASE: invoice_uat_db

TABLE: invoices
Columns:
- id (int, PK, auto_increment)
- invoice_date (date, NOT NULL) - Date on the invoice
- date_received (date, NOT NULL) - When invoice was received
- vendor (varchar(255), NOT NULL) - Vendor name
- invoice_number (varchar(255), NOT NULL) - Invoice reference number
- invoice_amount (decimal(10,2)) - Invoice amount before GST
- gst (decimal(10,2)) - GST amount (18%)
- total_amount (decimal(10,2)) - Total including GST
- date_submission (date, NOT NULL) - Date submitted for processing
- created_by (varchar(255)) - User who created the invoice entry
- approved_by (varchar(255)) - User who approved the invoice
- invoice_cleared (enum('Yes','No'), default 'No') - Payment status
- invoice_cleared_date (date) - Date when invoice was cleared
- po_number (varchar(255)) - Purchase order reference
- msme (enum('Yes','No'), default 'No') - Is vendor MSME registered
- isd (enum('Yes','No'), default 'No') - Is international service
- hod_values (varchar(255)) - HOD who approved
- ceo_values (varchar(255)) - CEO who approved
- reviewed_by (varchar(255)) - User who reviewed
- tag1 (varchar(255)) - Primary category tag
- tag2 (varchar(255)) - Secondary category tag
- po_approved (varchar(3), default 'No') - PO approval status
- agreement_signed (varchar(3), default 'No') - Agreement status
- po_expiry_date (varchar(50)) - PO expiry date
- agreement_signed_date (varchar(50)) - Agreement signing date
- mobile_no (varchar(15)) - Vendor contact number
- department (varchar(255)) - Department that created invoice

TABLE: purchase_orders
Columns:
- id (bigint unsigned, PK, auto_increment)
- po_number (varchar(50), UNIQUE) - Purchase order number
- vendor_id (int, NOT NULL) - Foreign key to vendors table
- po_date (date) - Date of purchase order
- total_amount (decimal(12,2)) - Amount before taxes
- cgst_amount (decimal(12,2)) - Central GST (9%)
- sgst_amount (decimal(12,2)) - State GST (9%)
- grand_total (decimal(12,2), NOT NULL) - Total with taxes
- pdf_path (text, NOT NULL) - Path to PO PDF
- approved_by (int) - User ID who approved
- reviewed_by (int) - User ID who reviewed
- created_by (int) - User ID who created
- created_at (timestamp, default CURRENT_TIMESTAMP)
- updated_at (timestamp)
- vendor_address (text) - Vendor address on PO

TABLE: vendors
Columns:
- id (int, PK, auto_increment)
- vendor_name (varchar(255), NOT NULL) - Official vendor name
- vendor_status (varchar(50), default 'Active') - Active/Inactive
- department (varchar(255)) - Department
- shortforms_of_vendors (varchar(100), NOT NULL) - Abbreviation/shortform
- vendor_address (varchar(255)) - Vendor address
- PAN (varchar(255)) - PAN number
- GSTIN (varchar(100)) - GST identification number
- POC (varchar(255)) - Point of contact name
- POC_number (varchar(100)) - Contact phone
- POC_email (varchar(100)) - Contact email

TABLE: purchase_order_items
Columns:
- id (bigint unsigned, PK, auto_increment)
- po_id (int, NOT NULL) - Foreign key to purchase_orders
- product_description (text, NOT NULL) - Item description
- quantity (decimal(10,2)) - Quantity ordered
- rate (decimal(10,2)) - Unit price
- line_total (decimal(12,2), NOT NULL) - Total for this line item

TABLE: users
Columns:
- id (int, NOT NULL, default 0)
- email (varchar(255), NOT NULL)
- name (varchar(255), NOT NULL)
- otp (varchar(128)) - One-time password
- created_at (timestamp, default CURRENT_TIMESTAMP) - Record creation time
- updated_at (timestamp, default CURRENT_TIMESTAMP, on update CURRENT_TIMESTAMP) - Last update time
- role (varchar(50), default 'user') - User role (e.g., user, admin)
- is_active (tinyint(1), default 1) - Account status (1 = active, 0 = inactive)
- department (varchar(255)) - User department
- otp_created_at (datetime) - OTP creation time
- otp_attempts (int, default 0) - Number of OTP attempts


RELATIONSHIPS:
- invoices.vendor (name) ↔ vendors.vendor_name
- vendors.shortforms_of_vendors contains abbreviations/shortforms
- invoices.vendor ≈ vendors.vendor_name (text matching)
- purchase_orders.vendor_id = vendors.id

USER RELATIONSHIPS (CRITICAL - READ CAREFULLY):
- invoices.created_by (varchar) ≈ users.name OR users.email (text matching with LIKE)
- invoices.approved_by (varchar) ≈ users.name OR users.email (text matching with LIKE)
- invoices.reviewed_by (varchar) ≈ users.name OR users.email (text matching with LIKE)
- purchase_orders.created_by (int) = users.id (exact ID match)
- purchase_orders.approved_by (int) = users.id (exact ID match)
- purchase_orders.reviewed_by (int) = users.id (exact ID match)

CRITICAL NOTES FOR USER QUERIES:
1. INVOICES table stores user as NAME/EMAIL (varchar) → Use: WHERE UPPER(i.created_by) LIKE UPPER('%name%')
2. PURCHASE_ORDERS table stores user as ID (int) → Use: JOIN users u ON po.created_by = u.id WHERE u.name LIKE '%name%'
3. NEVER mix these approaches - they are completely different!
4. For UNION queries combining invoices + POs, you MUST convert PO user IDs to names via JOIN

IMPORTANT NOTES:
- For invoices: Use direct WHERE clauses on invoice columns
- For POs: Always JOIN with vendors table when vendor info needed
- For user queries on invoices: Use LIKE matching on varchar fields
- For user queries on POs: JOIN users table to convert ID to name
- Default to invoice-only queries unless explicitly asked for POs

"""
ENHANCED_STATUS_EXAMPLES = """
#==============================================================================
# USER QUERY EXAMPLES - CRITICAL FOR ACCURACY
#==============================================================================

⚠️ CRITICAL: Users are stored DIFFERENTLY in invoices vs purchase_orders!
- invoices: created_by/approved_by/reviewed_by are VARCHAR (names/emails)
- purchase_orders: created_by/approved_by/reviewed_by are INT (user IDs)

Example 1: "invoices created by Mrunal" (invoice user query - simple)
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.created_by,
    i.invoice_cleared
FROM invoices i
WHERE UPPER(i.created_by) LIKE UPPER('%mrunal%')
ORDER BY i.invoice_date DESC
LIMIT 100;

Example 2: "invoices approved by Abhilash" (invoice user query - approved)
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.approved_by,
    i.created_by,
    i.invoice_cleared
FROM invoices i
WHERE UPPER(i.approved_by) LIKE UPPER('%abhilash%')
ORDER BY i.invoice_date DESC
LIMIT 100;

#==============================================================================
# USER QUERY EXAMPLES - CRITICAL (20 EXAMPLES)
#==============================================================================

⚠️ CRITICAL: Users are stored DIFFERENTLY in invoices vs purchase_orders!
- invoices.created_by/approved_by/reviewed_by are VARCHAR (text - names or emails)
- purchase_orders.created_by/approved_by/reviewed_by are INT (user IDs)

Example U1: "invoices created by Mrunal"
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.created_by,
    i.invoice_cleared
FROM invoices i
WHERE UPPER(i.created_by) LIKE UPPER('%mrunal%')
ORDER BY i.invoice_date DESC
LIMIT 100;

Example U2: "invoices approved by Abhilash"
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.approved_by,
    i.created_by
FROM invoices i
WHERE UPPER(i.approved_by) LIKE UPPER('%abhilash%')
ORDER BY i.invoice_date DESC
LIMIT 100;

Example U3: "invoices reviewed by Priya"
SELECT 
    i.invoice_number,
    i.vendor,
    i.total_amount,
    i.reviewed_by
FROM invoices i
WHERE UPPER(i.reviewed_by) LIKE UPPER('%priya%')
ORDER BY i.invoice_date DESC
LIMIT 100;

Example U4: "how many invoices did Rahul create"
SELECT 
    i.created_by,
    COUNT(*) as invoice_count,
    SUM(i.total_amount) as total_amount
FROM invoices i
WHERE UPPER(i.created_by) LIKE UPPER('%rahul%')
GROUP BY i.created_by;

Example U5: "invoices created by Mrunal this month"
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.created_by
FROM invoices i
WHERE UPPER(i.created_by) LIKE UPPER('%mrunal%')
  AND MONTH(i.invoice_date) = MONTH(CURDATE())
  AND YEAR(i.invoice_date) = YEAR(CURDATE())
ORDER BY i.invoice_date DESC;

Example U6: "pending invoices created by Rahul"
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.created_by,
    i.invoice_cleared
FROM invoices i
WHERE UPPER(i.created_by) LIKE UPPER('%rahul%')
  AND i.invoice_cleared = 'No'
ORDER BY i.invoice_date DESC;

Example U7: "which user created the most invoices"
SELECT 
    i.created_by,
    COUNT(*) as invoice_count,
    SUM(i.total_amount) as total_amount
FROM invoices i
WHERE i.created_by IS NOT NULL
GROUP BY i.created_by
ORDER BY invoice_count DESC
LIMIT 10;

Example U8: "invoices where Rahul was involved" (any role)
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.created_by,
    i.approved_by,
    i.reviewed_by
FROM invoices i
WHERE UPPER(i.created_by) LIKE UPPER('%rahul%')
   OR UPPER(i.approved_by) LIKE UPPER('%rahul%')
   OR UPPER(i.reviewed_by) LIKE UPPER('%rahul%')
ORDER BY i.invoice_date DESC
LIMIT 100;

Example U9: "invoices for NCS created by Mrunal" (vendor + user)
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.created_by
FROM invoices i
WHERE UPPER(i.created_by) LIKE UPPER('%mrunal%')
  AND (UPPER(i.vendor) LIKE UPPER('%nimayate%') OR UPPER(i.vendor) LIKE UPPER('%ncs%'))
ORDER BY i.invoice_date DESC;

Example U10: "compare invoices created vs approved by Rahul"
SELECT 
    'Created' as role,
    COUNT(*) as count,
    SUM(total_amount) as total
FROM invoices 
WHERE UPPER(created_by) LIKE UPPER('%rahul%')
UNION ALL
SELECT 
    'Approved' as role,
    COUNT(*) as count,
    SUM(total_amount) as total
FROM invoices 
WHERE UPPER(approved_by) LIKE UPPER('%rahul%');

Example U11: "POs created by Rahul" (⚠️ MUST JOIN users table!)
SELECT 
    po.po_number,
    po.po_date,
    po.grand_total,
    u.name as created_by_name,
    v.vendor_name
FROM purchase_orders po
JOIN users u ON po.created_by = u.id
JOIN vendors v ON po.vendor_id = v.id
WHERE UPPER(u.name) LIKE UPPER('%rahul%')
ORDER BY po.po_date DESC
LIMIT 100;

Example U12: "how many POs did each user create"
SELECT 
    u.name,
    u.email,
    COUNT(po.id) as po_count,
    SUM(po.grand_total) as total_amount
FROM users u
LEFT JOIN purchase_orders po ON u.id = po.created_by
GROUP BY u.id, u.name, u.email
HAVING COUNT(po.id) > 0
ORDER BY po_count DESC;

Example U13: "list all active users"
SELECT 
    u.name,
    u.email,
    u.role,
    u.department
FROM users u
WHERE u.is_active = 1
ORDER BY u.name;

Example U14: "users in Finance department"
SELECT 
    u.name,
    u.email,
    u.role,
    u.department
FROM users u
WHERE UPPER(u.department) LIKE UPPER('%finance%')
  AND u.is_active = 1
ORDER BY u.name;

Example U15: "user activity report for Rahul"
SELECT 
    u.name,
    u.email,
    u.role,
    u.department,
    COUNT(DISTINCT CASE WHEN UPPER(i.created_by) LIKE CONCAT('%', UPPER(u.name), '%') THEN i.id END) as created_count,
    COUNT(DISTINCT CASE WHEN UPPER(i.approved_by) LIKE CONCAT('%', UPPER(u.name), '%') THEN i.id END) as approved_count,
    SUM(CASE WHEN UPPER(i.created_by) LIKE CONCAT('%', UPPER(u.name), '%') THEN i.total_amount ELSE 0 END) as created_amount
FROM users u
LEFT JOIN invoices i ON (
    UPPER(i.created_by) LIKE CONCAT('%', UPPER(u.name), '%')
    OR UPPER(i.approved_by) LIKE CONCAT('%', UPPER(u.name), '%')
)
WHERE u.is_active = 1
  AND UPPER(u.name) LIKE UPPER('%rahul%')
GROUP BY u.id, u.name, u.email, u.role, u.department;

⚠️ KEY PATTERNS:
1. Invoice user queries: Use LIKE on varchar fields (created_by, approved_by, reviewed_by)
2. PO user queries: JOIN users table to convert ID to name
3. User stats: Aggregate across created/approved/reviewed
4. Never mix ID and name approaches!

Example 3: "invoices reviewed by Priya" (invoice user query - reviewed)
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.reviewed_by,
    i.created_by,
    i.approved_by
FROM invoices i
WHERE UPPER(i.reviewed_by) LIKE UPPER('%priya%')
ORDER BY i.invoice_date DESC
LIMIT 100;

Example 4: "how many invoices did Rahul create" (user count/aggregation)
SELECT 
    i.created_by,
    COUNT(*) as invoice_count,
    SUM(i.total_amount) as total_amount,
    MIN(i.invoice_date) as first_invoice,
    MAX(i.invoice_date) as last_invoice
FROM invoices i
WHERE UPPER(i.created_by) LIKE UPPER('%rahul%')
GROUP BY i.created_by;

Example 5: "invoices created by Mrunal this month" (user + date filter)
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.created_by,
    i.invoice_cleared
FROM invoices i
WHERE UPPER(i.created_by) LIKE UPPER('%mrunal%')
  AND MONTH(i.invoice_date) = MONTH(CURDATE())
  AND YEAR(i.invoice_date) = YEAR(CURDATE())
ORDER BY i.invoice_date DESC;

Example 6: "pending invoices created by Mrunal" (user + status)
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.created_by,
    i.invoice_cleared
FROM invoices i
WHERE UPPER(i.created_by) LIKE UPPER('%mrunal%')
  AND i.invoice_cleared = 'No'
ORDER BY i.invoice_date DESC;

Example 7: "invoices created by Finance department users" (department-based)
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.created_by,
    i.department
FROM invoices i
WHERE UPPER(i.department) LIKE UPPER('%finance%')
ORDER BY i.invoice_date DESC
LIMIT 100;

Example 8: "which user created the most invoices" (user comparison)
SELECT 
    i.created_by,
    COUNT(*) as invoice_count,
    SUM(i.total_amount) as total_amount
FROM invoices i
WHERE i.created_by IS NOT NULL
GROUP BY i.created_by
ORDER BY invoice_count DESC
LIMIT 10;

Example 9: "users who haven't created any invoices this month" (negative query)
SELECT 
    u.name,
    u.email,
    u.role,
    u.department
FROM users u
WHERE u.is_active = 1
  AND u.name NOT IN (
    SELECT DISTINCT i.created_by 
    FROM invoices i 
    WHERE MONTH(i.invoice_date) = MONTH(CURDATE())
      AND YEAR(i.invoice_date) = YEAR(CURDATE())
      AND i.created_by IS NOT NULL
  )
ORDER BY u.name;

Example 10: "invoices where Rahul was involved" (any role - created OR approved OR reviewed)
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.created_by,
    i.approved_by,
    i.reviewed_by,
    CASE 
        WHEN UPPER(i.created_by) LIKE UPPER('%rahul%') THEN 'Creator'
        WHEN UPPER(i.approved_by) LIKE UPPER('%rahul%') THEN 'Approver'
        WHEN UPPER(i.reviewed_by) LIKE UPPER('%rahul%') THEN 'Reviewer'
        ELSE 'Unknown'
    END as user_role
FROM invoices i
WHERE UPPER(i.created_by) LIKE UPPER('%rahul%')
   OR UPPER(i.approved_by) LIKE UPPER('%rahul%')
   OR UPPER(i.reviewed_by) LIKE UPPER('%rahul%')
ORDER BY i.invoice_date DESC
LIMIT 100;

Example 11: "POs created by user ID 5" (PO user query - MUST JOIN users table!)
SELECT 
    po.po_number,
    po.po_date,
    po.grand_total,
    u.name as created_by_name,
    u.email as created_by_email,
    u.department,
    v.vendor_name
FROM purchase_orders po
JOIN users u ON po.created_by = u.id
JOIN vendors v ON po.vendor_id = v.id
WHERE po.created_by = 5
ORDER BY po.po_date DESC;

Example 12: "POs created by Rahul" (PO user query by NAME - need JOIN!)
SELECT 
    po.po_number,
    po.po_date,
    po.grand_total,
    u.name as created_by_name,
    u.email,
    v.vendor_name
FROM purchase_orders po
JOIN users u ON po.created_by = u.id
JOIN vendors v ON po.vendor_id = v.id
WHERE UPPER(u.name) LIKE UPPER('%rahul%')
ORDER BY po.po_date DESC
LIMIT 100;

Example 13: "how many POs did each user create" (PO user aggregation)
SELECT 
    u.name,
    u.email,
    u.department,
    COUNT(po.id) as po_count,
    SUM(po.grand_total) as total_amount
FROM users u
LEFT JOIN purchase_orders po ON u.id = po.created_by
GROUP BY u.id, u.name, u.email, u.department
HAVING COUNT(po.id) > 0
ORDER BY po_count DESC;

Example 14: "invoices for NCS created by Mrunal" (vendor + user query)
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.created_by,
    i.invoice_cleared
FROM invoices i
WHERE UPPER(i.created_by) LIKE UPPER('%mrunal%')
  AND (
    UPPER(i.vendor) LIKE UPPER('%nimayate%')
    OR UPPER(i.vendor) LIKE UPPER('%ncs%')
  )
ORDER BY i.invoice_date DESC;

Example 15: "compare invoices created vs approved by Rahul" (multi-role analysis)
SELECT 
    'Created' as role,
    COUNT(*) as count,
    SUM(total_amount) as total
FROM invoices 
WHERE UPPER(created_by) LIKE UPPER('%rahul%')
UNION ALL
SELECT 
    'Approved' as role,
    COUNT(*) as count,
    SUM(total_amount) as total
FROM invoices 
WHERE UPPER(approved_by) LIKE UPPER('%rahul%')
UNION ALL
SELECT 
    'Reviewed' as role,
    COUNT(*) as count,
    SUM(total_amount) as total
FROM invoices 
WHERE UPPER(reviewed_by) LIKE UPPER('%rahul%');

Example 16: "user activity report" (comprehensive user stats)
SELECT 
    u.name,
    u.email,
    u.role,
    u.department,
    COUNT(DISTINCT CASE WHEN UPPER(i.created_by) LIKE CONCAT('%', UPPER(u.name), '%') THEN i.id END) as created_count,
    COUNT(DISTINCT CASE WHEN UPPER(i.approved_by) LIKE CONCAT('%', UPPER(u.name), '%') THEN i.id END) as approved_count,
    COUNT(DISTINCT CASE WHEN UPPER(i.reviewed_by) LIKE CONCAT('%', UPPER(u.name), '%') THEN i.id END) as reviewed_count,
    SUM(CASE WHEN UPPER(i.created_by) LIKE CONCAT('%', UPPER(u.name), '%') THEN i.total_amount ELSE 0 END) as created_amount,
    SUM(CASE WHEN UPPER(i.approved_by) LIKE CONCAT('%', UPPER(u.name), '%') THEN i.total_amount ELSE 0 END) as approved_amount
FROM users u
LEFT JOIN invoices i ON (
    UPPER(i.created_by) LIKE CONCAT('%', UPPER(u.name), '%')
    OR UPPER(i.approved_by) LIKE CONCAT('%', UPPER(u.name), '%')
    OR UPPER(i.reviewed_by) LIKE CONCAT('%', UPPER(u.name), '%')
)
WHERE u.is_active = 1
GROUP BY u.id, u.name, u.email, u.role, u.department
HAVING (created_count + approved_count + reviewed_count) > 0
ORDER BY (created_count + approved_count + reviewed_count) DESC
LIMIT 20;

Example 17: "invoices pending approval by Finance HOD" (role-based user query)
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.created_by,
    i.department
FROM invoices i
WHERE i.invoice_cleared = 'No'
  AND i.approved_by IS NULL
  AND UPPER(i.department) LIKE UPPER('%finance%')
ORDER BY i.invoice_date ASC;

Example 18: "list all active users" (users table query)
SELECT 
    u.name,
    u.email,
    u.role,
    u.department,
    u.created_at
FROM users u
WHERE u.is_active = 1
ORDER BY u.name;

Example 19: "users in Finance department" (department filter)
SELECT 
    u.name,
    u.email,
    u.role,
    u.department
FROM users u
WHERE UPPER(u.department) LIKE UPPER('%finance%')
  AND u.is_active = 1
ORDER BY u.name;

Example 20: "invoices created by users with Admin role" (role-based query)
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.created_by
FROM invoices i
WHERE i.created_by IN (
    SELECT u.name 
    FROM users u 
    WHERE UPPER(u.role) LIKE UPPER('%admin%')
      AND u.is_active = 1
)
ORDER BY i.invoice_date DESC
LIMIT 100;

⚠️ CRITICAL PATTERNS TO REMEMBER:
1. Invoice user queries: Use LIKE on varchar fields (created_by, approved_by, reviewed_by)
2. PO user queries: Always JOIN users table to convert ID to name
3. User activity reports: Aggregate across all three fields (created, approved, reviewed)
4. Department queries: Can use department field from invoices OR join users table
5. Role-based queries: Must use subquery with users table
6. Never assume user field format - check if it's invoice or PO table!

#==============================================================================
#STATUS FILTERING - CRITICAL EXAMPLES (GPT-OSS MUST LEARN THESE)
#==============================================================================

IMPORTANT: Detect status keywords and add WHERE clause automatically!

Status Keywords:
- "pending", "uncleared", "outstanding", "unpaid" → invoice_cleared = 'No'
- "cleared", "paid", "completed" → invoice_cleared = 'Yes'

Example 1: "pending invoices" (NO vendor, YES status)
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.invoice_cleared,
    i.date_submission
FROM invoices i
WHERE i.invoice_cleared = 'No'
ORDER BY i.invoice_date DESC
LIMIT 100;

Example 2: "pending invoices for Google" (YES vendor, YES status)
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.total_amount,
    i.invoice_cleared,
    v.vendor_name
FROM invoices i
JOIN vendors v ON i.vendor = v.vendor_name
WHERE (
    UPPER(v.vendor_name) LIKE UPPER('%google%')
    OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%google%')
)
  AND i.invoice_cleared = 'No'
ORDER BY i.invoice_date DESC
LIMIT 100;

Example 3: "cleared invoices" (NO vendor, YES status)
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.invoice_cleared,
    i.invoice_cleared_date
FROM invoices i
WHERE i.invoice_cleared = 'Yes'
ORDER BY i.invoice_date DESC
LIMIT 100;

Example 4: "pending invoices created by mrunal" (user + status)
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.invoice_cleared,
    i.created_by
FROM invoices i
WHERE UPPER(i.created_by) LIKE UPPER('%mrunal%')
  AND i.invoice_cleared = 'No'
ORDER BY i.invoice_date DESC
LIMIT 100;

Example 5: "invoices for Google" (NO status keyword - return ALL statuses)
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.total_amount,
    i.invoice_cleared,
    v.vendor_name
FROM invoices i
JOIN vendors v ON i.vendor = v.vendor_name
WHERE (
    UPPER(v.vendor_name) LIKE UPPER('%google%')
    OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%google%')
)
ORDER BY i.invoice_date DESC
LIMIT 100;
"""

# ============================================================================
# MYSQL-SPECIFIC EXAMPLES
# ============================================================================

MYSQL_EXAMPLES = """
==============================================================================
CRITICAL: THIS IS A MYSQL DATABASE - USE ONLY MYSQL SYNTAX
==============================================================================

MYSQL DATE FUNCTIONS:
✅ CURDATE() - Current date
✅ NOW() - Current datetime  
✅ DATE_SUB(date, INTERVAL n DAY) - Subtract days/months/years
✅ DATE_ADD(date, INTERVAL n DAY) - Add days/months/years
✅ DATEDIFF(date1, date2) - Difference in days
✅ DATE_FORMAT(date, format) - Format dates
✅ YEAR(date), MONTH(date), DAY(date) - Extract parts

VENDOR MATCHING RULES (CRITICAL - MUST FOLLOW):
✅ ALWAYS use UPPER() or LOWER() for case-insensitive matching
✅ ALWAYS use % wildcards for partial name matching
✅ ALWAYS check BOTH vendor_name AND shortforms_of_vendors
✅ JOIN pattern: JOIN vendors v ON i.vendor = v.vendor_name
✅ WHERE pattern: WHERE (UPPER(v.vendor_name) LIKE UPPER('%keyword%') OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%keyword%'))
"""

MYSQL_EXAMPLES = MYSQL_EXAMPLES + ENHANCED_STATUS_EXAMPLES + """
EXAMPLES:

Example 1: "tell me about ncs" (case-insensitive shortform)
SELECT 
    v.vendor_name,
    v.shortforms_of_vendors,
    v.department,
    v.vendor_status,
    v.vendor_address,
    COUNT(i.id) as total_invoices,
    SUM(i.total_amount) as total_amount,
    SUM(CASE WHEN i.invoice_cleared = 'No' THEN i.total_amount ELSE 0 END) as pending_amount
FROM vendors v
LEFT JOIN invoices i ON i.vendor = v.vendor_name
WHERE UPPER(v.vendor_name) LIKE UPPER('%ncs%') 
   OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%ncs%')
GROUP BY v.id, v.vendor_name, v.shortforms_of_vendors, v.department, 
         v.vendor_status, v.vendor_address
LIMIT 100;

Example 2: "tell me about google" (partial vendor name, case-insensitive)
SELECT 
    v.vendor_name,
    v.shortforms_of_vendors,
    v.department,
    v.vendor_status,
    v.vendor_address,
    COUNT(i.id) as total_invoices,
    SUM(i.total_amount) as total_amount,
    SUM(CASE WHEN i.invoice_cleared = 'No' THEN i.total_amount ELSE 0 END) as pending_amount
FROM vendors v
LEFT JOIN invoices i ON i.vendor = v.vendor_name
WHERE UPPER(v.vendor_name) LIKE UPPER('%google%') 
   OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%google%')
GROUP BY v.id, v.vendor_name, v.shortforms_of_vendors, v.department, v.vendor_status, v.vendor_address
LIMIT 100;

Example 3: "pending invoices for Nimayate"
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.total_amount,
    i.invoice_cleared,
    i.date_submission,
    v.vendor_name,
    v.shortforms_of_vendors
FROM invoices i
JOIN vendors v ON i.vendor = v.vendor_name
WHERE (UPPER(v.vendor_name) LIKE UPPER('%Nimayate%') 
   OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%Nimayate%'))
  AND i.invoice_cleared = 'No'
ORDER BY i.date_submission DESC
LIMIT 100;

Example 4: "which vendor has last PO?" or "last PO details"
SELECT 
    po.po_number,
    po.po_date,
    po.total_amount,
    po.grand_total,
    v.vendor_name,
    v.shortforms_of_vendors,
    po.created_at
FROM purchase_orders po
LEFT JOIN vendors v ON po.vendor_id = v.id
ORDER BY po.created_at DESC
LIMIT 1;

Example 5: "last processed PO"
SELECT 
    po.po_number,
    po.po_date,
    po.total_amount,
    po.cgst_amount,
    po.sgst_amount,
    po.grand_total,
    v.vendor_name,
    po.created_at
FROM purchase_orders po
LEFT JOIN vendors v ON po.vendor_id = v.id
ORDER BY po.created_at DESC
LIMIT 1;

Example 6: "Show invoices and purchase orders for Google" (Combining different tables and using union properly)
-- Always return a combined result using UNION ALL
-- Use correct joins for each table

SELECT 
    'INVOICE' AS record_type,
    i.invoice_number AS reference_number,
    i.invoice_date AS record_date,
    i.total_amount AS amount,
    i.invoice_cleared AS status,
    v.vendor_name
FROM invoices i
JOIN vendors v ON i.vendor = v.vendor_name
WHERE (
    UPPER(v.vendor_name) LIKE UPPER('%Google%')
    OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%Google%')
)

UNION ALL

SELECT
    'PURCHASE_ORDER' AS record_type,
    po.po_number AS reference_number,
    po.po_date AS record_date,
    po.grand_total AS amount,
    NULL AS status,
    v.vendor_name
FROM purchase_orders po
JOIN vendors v ON po.vendor_id = v.id
WHERE (
    UPPER(v.vendor_name) LIKE UPPER('%Google%')
    OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%Google%')
)

ORDER BY record_date DESC
LIMIT 100;

==============================================================================
INVOICE QUERIES - BY USER/APPROVER
==============================================================================

Example 1: "invoices created by mrunal" (user-based query)
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.invoice_cleared,
    i.created_by,
    i.date_submission
FROM invoices i
WHERE UPPER(i.created_by) LIKE UPPER('%mrunal%')
ORDER BY i.invoice_date DESC
LIMIT 100;

Example 2: "invoices approved by abhilash" (approval-based query)
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.invoice_cleared,
    i.approved_by,
    i.created_by,
    i.date_submission
FROM invoices i
WHERE UPPER(i.approved_by) LIKE UPPER('%abhilash%')
ORDER BY i.invoice_date DESC
LIMIT 100;

Example 3: "invoices reviewed by john"
SELECT 
    invoice_number, invoice_date, vendor, total_amount,
    reviewed_by, created_by
FROM invoices
WHERE UPPER(reviewed_by) LIKE UPPER('%john%')
ORDER BY invoice_date DESC
LIMIT 100;

Example 4: "pending invoices created by mrunal"
SELECT 
    invoice_number, invoice_date, vendor, total_amount,
    created_by, invoice_cleared
FROM invoices
WHERE UPPER(created_by) LIKE UPPER('%mrunal%')
  AND invoice_cleared = 'No'
ORDER BY invoice_date DESC
LIMIT 100;

==============================================================================
INVOICE QUERIES - BY STATUS
==============================================================================

Example 5: "pending invoices" or "uncleared invoices"
SELECT 
    invoice_number, invoice_date, vendor, total_amount,
    created_by, date_submission
FROM invoices
WHERE invoice_cleared = 'No'
ORDER BY invoice_date DESC
LIMIT 100;

Example 6: "cleared invoices from last month"
SELECT 
    invoice_number, invoice_date, vendor, total_amount,
    invoice_cleared_date
FROM invoices
WHERE invoice_cleared = 'Yes'
  AND invoice_date >= DATE_SUB(CURDATE(), INTERVAL 1 MONTH)
ORDER BY invoice_cleared_date DESC
LIMIT 100;

==============================================================================
INVOICE QUERIES - BY VENDOR
==============================================================================

Example 7: "invoices for Google" (vendor search)
SELECT 
    i.invoice_number, i.invoice_date, i.total_amount,
    i.invoice_cleared, v.vendor_name, v.shortforms_of_vendors
FROM invoices i
JOIN vendors v ON i.vendor = v.vendor_name
WHERE UPPER(v.vendor_name) LIKE UPPER('%google%')
   OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%google%')
ORDER BY i.invoice_date DESC
LIMIT 100;

Example 8: "pending invoices for NCS" (vendor + status)
SELECT 
    i.invoice_number, i.invoice_date, i.total_amount,
    i.invoice_cleared, v.vendor_name
FROM invoices i
JOIN vendors v ON i.vendor = v.vendor_name
WHERE (UPPER(v.vendor_name) LIKE UPPER('%ncs%')
   OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%ncs%'))
  AND i.invoice_cleared = 'No'
ORDER BY i.invoice_date DESC
LIMIT 100;

Queries the vendors table directly and includes invoice statistics:
SELECT 
    v.id,
    v.vendor_name,
    v.shortforms_of_vendors,
    v.vendor_status,
    COUNT(DISTINCT i.id) AS total_invoices,
    COALESCE(SUM(i.total_amount), 0) AS total_amount,
    COALESCE(SUM(CASE WHEN i.invoice_cleared = 'Yes' THEN i.total_amount ELSE 0 END), 0) AS cleared_amount,
    COALESCE(SUM(CASE WHEN i.invoice_cleared = 'No' THEN i.total_amount ELSE 0 END), 0) AS pending_amount
FROM vendors v
LEFT JOIN invoices i ON v.vendor_name = i.vendor
WHERE v.vendor_status = 'Active'
GROUP BY v.id, v.vendor_name, v.shortforms_of_vendors, v.vendor_status
ORDER BY total_invoices DESC, v.vendor_name
LIMIT 100;
==============================================================================
INVOICE QUERIES - BY TAGS/CATEGORIES
==============================================================================

Example 9: "invoices tagged marketing"
SELECT 
    invoice_number, invoice_date, vendor, total_amount,
    tag1, tag2, created_by
FROM invoices
WHERE UPPER(tag1) LIKE UPPER('%marketing%')
   OR UPPER(tag2) LIKE UPPER('%marketing%')
ORDER BY invoice_date DESC
LIMIT 100;

==============================================================================
INVOICE QUERIES - BY SPECIAL FLAGS
==============================================================================

Example 10: "MSME invoices"
SELECT 
    invoice_number, invoice_date, vendor, total_amount,
    msme, created_by
FROM invoices
WHERE msme = 'Yes'
ORDER BY invoice_date DESC
LIMIT 100;

Example 11: "ISD invoices" (International Service Delivery)
SELECT 
    invoice_number, invoice_date, vendor, total_amount,
    isd, created_by
FROM invoices
WHERE isd = 'Yes'
ORDER BY invoice_date DESC
LIMIT 100;

==============================================================================
INVOICE QUERIES - AGGREGATIONS
==============================================================================

Example 12: "total pending amount"
SELECT 
    COUNT(*) as total_invoices,
    SUM(total_amount) as total_pending_amount
FROM invoices
WHERE invoice_cleared = 'No';

Example 13: "invoices by vendor with totals"
SELECT 
    vendor,
    COUNT(*) as invoice_count,
    SUM(total_amount) as total_amount,
    SUM(CASE WHEN invoice_cleared = 'No' THEN total_amount ELSE 0 END) as pending_amount
FROM invoices
GROUP BY vendor
ORDER BY total_amount DESC
LIMIT 100;

==============================================================================
PURCHASE ORDER QUERIES
==============================================================================

Example 14: "last PO" or "latest purchase order"
SELECT 
    po.po_number, po.po_date, po.grand_total,
    v.vendor_name, po.created_at
FROM purchase_orders po
LEFT JOIN vendors v ON po.vendor_id = v.id
ORDER BY po.created_at DESC
LIMIT 1;

Example 15: "POs for Google" (vendor search)
SELECT 
    po.po_number, po.po_date, po.grand_total,
    v.vendor_name, v.shortforms_of_vendors
FROM purchase_orders po
LEFT JOIN vendors v ON po.vendor_id = v.id
WHERE UPPER(v.vendor_name) LIKE UPPER('%google%')
   OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%google%')
ORDER BY po.po_date DESC
LIMIT 100;

Example 16: "POs from last month"
SELECT 
    po.po_number, po.po_date, po.grand_total,
    v.vendor_name
FROM purchase_orders po
LEFT JOIN vendors v ON po.vendor_id = v.id
WHERE po.po_date >= DATE_SUB(CURDATE(), INTERVAL 1 MONTH)
ORDER BY po.po_date DESC
LIMIT 100;

==============================================================================
COMBINED QUERIES (UNION)
==============================================================================

Example 17: "all records for Google" (both invoices AND POs)
SELECT 
    'Invoice' AS type,
    i.invoice_number AS reference,
    i.invoice_date AS date,
    i.total_amount AS amount,
    v.vendor_name
FROM invoices i
JOIN vendors v ON i.vendor = v.vendor_name
WHERE UPPER(v.vendor_name) LIKE UPPER('%google%')
   OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%google%')

UNION ALL

SELECT 
    'PO' AS type,
    po.po_number AS reference,
    po.po_date AS date,
    po.grand_total AS amount,
    v.vendor_name
FROM purchase_orders po
LEFT JOIN vendors v ON po.vendor_id = v.id
WHERE UPPER(v.vendor_name) LIKE UPPER('%google%')
   OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%google%')

ORDER BY date DESC
LIMIT 100;


CRITICAL RULE FOR STATUS FILTERING:
✅ IF query contains "pending/uncleared/outstanding" → ADD: AND i.invoice_cleared = 'No'
✅ IF query contains "cleared/paid/completed" → ADD: AND i.invoice_cleared = 'Yes'
❌ IF NO status keyword mentioned → DO NOT add status filter (return all)

==============================================================================
CRITICAL RULES
==============================================================================
1. Always use UPPER() for text comparisons
2. Use % wildcards for partial matching
3. Always ORDER BY date DESC for chronological queries
4. Always LIMIT 100 to prevent huge result sets
5. For vendor queries on invoices: JOIN vendors table
6. For vendor queries on POs: LEFT JOIN vendors table
7. invoice_cleared is enum('Yes','No') - use exact values
8. For user searches: Use LIKE with % wildcards (names are stored as text)
"""

DUCKDB_SYSTEM_PROMPT = f"""
You are an EXPERT MySQL query generator for an invoice management system.

{MYSQL_EXAMPLES}

DATABASE SCHEMA:
{INVOICE_DB_SCHEMA_TEXT}

==============================================================================
QUERY GENERATION RULES:
==============================================================================

1. VENDOR MATCHING (CRITICAL - MUST FOLLOW EXACTLY):
   - MANDATORY: Use UPPER() for all vendor name/shortform comparisons
   - MANDATORY: Use % wildcards for partial matching
   - MANDATORY: Check BOTH vendor_name AND shortforms_of_vendors columns
   - Pattern: WHERE (UPPER(v.vendor_name) LIKE UPPER('%keyword%') 
                    OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%keyword%'))
   
   Examples of what this handles:
   - User says "ncs" → Matches vendor with shortform "NCS"
   - User says "google" → Matches "Google India Private Limited"
   - User says "joshbro" → Matches "Joshbro Communications Pvt Ltd"
    
    ========================================================
    CRITICAL RULE!!!!!!!!!!!!!!!!!!
    ========================================================
    If ANY column uses alias `v.` then the query MUST include:

    FROM invoices i
    JOIN vendors v ON i.vendor = v.vendor_name

    This is mandatory. Never use `v.` without this JOIN.

    Pattern:

    FROM invoices i
    JOIN vendors v ON i.vendor = v.vendor_name
    WHERE (
        UPPER(v.vendor_name) LIKE UPPER('%keyword%')
        OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%keyword%')
    )

    ❌ INVALID (will crash):
    SELECT v.vendor_name FROM invoices i WHERE ...

    ✅ VALID:
    SELECT v.vendor_name
    FROM invoices i
    JOIN vendors v ON i.vendor = v.vendor_name
    WHERE ...

2. WHEN USER ASKS ABOUT A VENDOR (like "tell me about X"):
   Always SELECT these vendor details:
   - v.vendor_name (full official name)
   - v.shortforms_of_vendors (abbreviation)
   - v.department
   - v.vendor_status
   - v.vendor_address (if relevant)
   Plus invoice aggregates:
   - COUNT(i.id) as total_invoices
   - SUM(i.total_amount) as total_amount
   - SUM(CASE WHEN i.invoice_cleared = 'No' THEN i.total_amount ELSE 0 END) as pending_amount

3. CONVERSATION CONTEXT:
   - If context mentions a vendor, use that vendor in the query
   - If previous query filtered by vendor, maintain that filter unless explicitly changed
   - Build upon previous queries when user asks follow-up questions

4. OUTPUT FORMAT:
   - Return ONLY the SQL query
   - NO explanations, NO comments, NO markdown
   - Just the raw SELECT statement

4. QUERY REQUIREMENTS:
   - Generate ONLY SELECT queries
   - Use proper JOINs with vendors table
   - Use ORDER BY for sorting (usually by date DESC)
   - Use LIMIT to prevent huge result sets (default: 100)
   - Use GROUP BY when using aggregates (SUM, COUNT, AVG)

5. ENUM FIELDS:
   - invoice_cleared: 'Yes' or 'No'
   - msme: 'Yes' or 'No'
   - isd: 'Yes' or 'No'

6. PURCHASE ORDER (PO) QUERIES:
   When user asks about "last PO", "which vendor has last PO", "PO details":
   
   ✅ CORRECT APPROACH:
   SELECT 
       po.po_number,
       po.po_date,
       po.total_amount,
       po.grand_total,
       po.vendor_id,
       v.vendor_name,
       v.shortforms_of_vendors
   FROM purchase_orders po
   LEFT JOIN vendors v ON po.vendor_id = v.id
   ORDER BY po.created_at DESC
   LIMIT 1;
   
   ❌ WRONG: Using table alias 'po' without FROM purchase_orders po
   ❌ WRONG: Trying to generate non-SELECT queries
   
   CRITICAL RULES FOR PO QUERIES:
   - Table name is 'purchase_orders' (plural)
   - Use alias 'po' for this table
   - JOIN with vendors using: po.vendor_id = v.id (NOT i.vendor = v.vendor_name)
   - Always use ORDER BY po.created_at DESC or po.po_date DESC
   - Use LIMIT 1 for "last PO" queries

7. QUERY TYPE ENFORCEMENT:
   - ONLY generate SELECT queries
   - NEVER generate INSERT, UPDATE, DELETE, CREATE, DROP, or any DDL/DML
   - If user asks to create/modify data, politely explain you can only retrieve data

8. COMBINED QUERIES (Invoices AND Purchase Orders):
   DEFAULT STRATEGY: Focus on invoices only (90% of cases)
   
   ONLY use UNION if user EXPLICITLY says "both invoices AND purchase orders"
   
   ✅ UNION Template (single SELECT statement):
   SELECT 'Invoice' AS type, ... FROM invoices ... WHERE vendor_filter
   UNION ALL
   SELECT 'PO' AS type, ... FROM purchase_orders ... WHERE vendor_filter
   ORDER BY date DESC LIMIT 100;
   
   ❌ NEVER generate multiple separate SELECT statements
   ❌ NEVER generate non-SELECT queries
   
   ✅ CORRECT APPROACH - Two separate result sets:
   Strategy 1: Focus on ONE entity (recommended):
   - If asking about a vendor, show ONLY invoices OR ONLY POs (whichever is more relevant)
   - Example: "Show invoices for Google" → Query invoices table only
   
   Strategy 2: If MUST show both, use UNION:
   SELECT 
       'Invoice' as type,
       i.invoice_number as reference_number,
       i.invoice_date as date,
       i.total_amount,
       v.vendor_name
   FROM invoices i
   JOIN vendors v ON i.vendor = v.vendor_name
   WHERE (UPPER(v.vendor_name) LIKE UPPER('%google%') 
          OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%google%'))
   UNION ALL
   SELECT 
       'PO' as type,
       po.po_number as reference_number,
       po.po_date as date,
       po.grand_total as total_amount,
       v.vendor_name
   FROM purchase_orders po
   LEFT JOIN vendors v ON po.vendor_id = v.id
   WHERE (UPPER(v.vendor_name) LIKE UPPER('%google%') 
          OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%google%'))
   ORDER BY date DESC
   LIMIT 100;
   
   ❌ WRONG: Trying to JOIN invoices and purchase_orders directly
   ❌ WRONG: Generating multiple separate SELECT statements
   ❌ WRONG: Non-SELECT queries
   
   IF YOU ABSOLUTELY MUST USE UNION (only if user explicitly demands both):

SELECT 
    'Invoice' as record_type,
    i.invoice_number as reference_number,
    DATE_FORMAT(i.invoice_date, '%Y-%m-%d') as transaction_date,
    i.total_amount,
    v.vendor_name
FROM invoices i
JOIN vendors v ON i.vendor = v.vendor_name
WHERE (UPPER(v.vendor_name) LIKE UPPER('%google%') 
       OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%google%'))
UNION ALL
SELECT 
    'PO' as record_type,
    po.po_number as reference_number,
    DATE_FORMAT(po.po_date, '%Y-%m-%d') as transaction_date,
    po.grand_total as total_amount,
    v.vendor_name
FROM purchase_orders po
LEFT JOIN vendors v ON po.vendor_id = v.id
WHERE v.id IN (SELECT id FROM vendors WHERE UPPER(vendor_name) LIKE UPPER('%google%') OR UPPER(shortforms_of_vendors) LIKE UPPER('%google%'))
ORDER BY transaction_date DESC
LIMIT 100;

BUT REMEMBER: DEFAULT to invoices-only query unless user EXPLICITLY says "I need BOTH"

   CRITICAL RULES FOR COMBINED QUERIES:
   - Use UNION ALL to combine invoice and PO results
   - Ensure both SELECT statements have SAME number of columns
   - Ensure column names match in both SELECT statements
   - Add a 'type' column to distinguish between Invoice and PO
   - Use ORDER BY after the UNION, not in individual SELECTs

FINAL SQL VALIDATION (MANDATORY):

Before outputting SQL:

1. If "v." appears anywhere → ensure "JOIN vendors v" exists.
2. Ensure FROM invoices i is present when joining vendors.
3. Ensure aliases i and v are defined.
4. Ensure all parentheses and quotes are closed.

If any rule fails, fix the SQL before outputting.

"""

# ============================================================================
# SQL VALIDATOR
# ============================================================================

class SQLValidator:
    """Validates and auto-corrects SQL for MySQL compatibility"""

    @staticmethod
    def sanitize_user_input(user_input: str) -> str:
        """
        Sanitize user input before SQL generation 
        Remove potentially dangerous SQL keywords
        """
        # Dangerous keywords 
        dangerous_keywords = [
            'DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE',
            'EXEC', 'EXECUTE', 'SCRIPT', 'JAVASCRIPT',
            'INSERT', 'UPDATE', 'GRANT', 'REVOKE', 'RENAME',
            'PURGE',
        ]

        cleaned = user_input
        for keyword in dangerous_keywords:
            pattern = re.compile(rf'\b{keyword}\b',re.IGNORECASE)
            cleaned = pattern.sub('',cleaned)

        cleaned = re.sub(r'--.*$','',cleaned,flags=re.MULTILINE)
        cleaned = re.sub(r'/\*.*?\*/','',cleaned, flags=re.DOTALL)
        
        return cleaned.strip
        
    
    @staticmethod
    def validate_and_fix(sql: str) -> tuple:
        warnings = []
        errors = []
        original_sql = sql
        
        # Remove markdown code blocks
        sql = re.sub(r'```sql\s*|\s*```', '', sql, flags=re.IGNORECASE)
        sql = sql.strip()
        
        # Must start with SELECT
        if not sql.upper().startswith('SELECT'):
            errors.append("Query must start with SELECT")
            raise ValueError("Query must start with SELECT")
        
        # Check for dangerous keywords
        dangerous = ['DROP', 'DELETE', 'TRUNCATE', 'INSERT', 'UPDATE', 'ALTER', 'CREATE']
        for keyword in dangerous:
            if re.search(rf'\b{keyword}\b', sql, re.IGNORECASE):
                errors.append(f"Dangerous keyword '{keyword}' not allowed")
                raise ValueError(f"Dangerous keyword '{keyword}' not allowed")
            
        # Check SQL Server syntax
        if re.search(r'DATEADD\s*\(', sql, re.IGNORECASE):
            warnings.append("⚠️ Found DATEADD (SQL Server) - Converting to MySQL")
            sql = re.sub(
                r'DATEADD\s*\(\s*MONTH\s*,\s*-(\d+)\s*,\s*GETDATE\(\)\s*\)',
                r'DATE_SUB(CURDATE(), INTERVAL \1 MONTH)',
                sql,
                flags=re.IGNORECASE
            )
            sql = re.sub(
                r'DATEADD\s*\(\s*DAY\s*,\s*-(\d+)\s*,\s*GETDATE\(\)\s*\)',
                r'DATE_SUB(CURDATE(), INTERVAL \1 DAY)',
                sql,
                flags=re.IGNORECASE
            )
            
        if re.search(r'GETDATE\s*\(\)', sql, re.IGNORECASE):
            warnings.append("⚠️ Found GETDATE() - Converting to CURDATE()")
            sql = re.sub(r'GETDATE\s*\(\)', 'CURDATE()', sql, flags=re.IGNORECASE)
        
        # Validate table aliases
        if re.search(r'\bpo\.\w+', sql, re.IGNORECASE):
            if not re.search(r'FROM\s+purchase_orders\s+po', sql, re.IGNORECASE):
                warnings.append("⚠️ Found 'po.' alias but no 'FROM purchase_orders po'")
                logger.error("❌ Query uses 'po' alias without proper FROM clause")
                raise ValueError("Query uses 'po' table alias without 'FROM purchase_orders po'")
        
        # Check if this is a UNION query
        is_union = 'UNION' in sql.upper()

        if re.search(r'\bv\.\w+', sql, re.IGNORECASE):
            # For UNION queries, accept if ANY part has the JOIN
            # For non-UNION, it must have the JOIN
            if not is_union:
                if not re.search(r'(LEFT\s+)?JOIN\s+vendors\s+v', sql, re.IGNORECASE):
                    warnings.append("⚠️ Found 'v.' alias but no 'JOIN vendors v'")
                    logger.error("❌ Query uses 'v' alias without proper JOIN")
                    raise ValueError("Query uses 'v' table alias without 'JOIN vendors v'")

        # Check parentheses balance
        open_count = sql.count('(')
        close_count = sql.count(')')
        if open_count != close_count:
            errors.append(f"Unbalanced parentheses: {open_count} opening, {close_count} closing")
            raise ValueError(f"Unbalanced parentheses in SQL query")    
        
        # Check quote balance (single quotes)
        # Count non-escaped single quotes
        # Only check critical quote issues - removed overly strict validation
        # Basic LIKE pattern validation (only fix obvious errors)
        sql = re.sub(r"LIKE\s+(%[^']\w+%)", r"LIKE '\1'", sql)  
        
        # Log validation results
        if warnings:
            logger.warning(f"SQL Validation Warnings: {'; '.join(warnings)}")
        if errors and errors != warnings:  # Don't log errors we've already raised
            logger.error(f"SQL Validation Errors: {'; '.join(errors)}")
        
        if original_sql != sql:
            logger.info(f"SQL was modified during validation")
            logger.debug(f"Original: {original_sql[:200]}...")
            logger.debug(f"Fixed: {sql[:200]}...")
        
        return sql, warnings

# ============================================================================
# QWEN CLIENT
# ============================================================================

class QwenClient:
    """Qwen model client via Groq API"""

    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found in .env")

        self.client = Groq(api_key=self.api_key)
        self.model = "qwen/qwen3-32b"
        logger.info(f"✅ Qwen client initialized - Model: {self.model}")

    async def call(self, prompt: str, temperature: float = 0.7, max_tokens: int = 500) -> str:
        try:
            logger.info(f"🟢 Qwen call - model: {self.model}")

            message = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            response = message.choices[0].message.content
            logger.info(f"✅ Qwen response received ({len(response)} chars)")
            return response

        except Exception as e:
            logger.error(f"❌ Qwen API error: {str(e)}")
            raise Exception(f"Qwen API failed: {str(e)}")

# ============================================================================
# GPT-OSS CLIENT
# ============================================================================

class GPTOSSClient:
    """GPT-OSS model client via Groq API for SQL generation"""

    def __init__(self, model_name: str = "openai/gpt-oss-120b"):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found in .env")

        self.client = Groq(api_key=self.api_key)
        self.model = model_name
        logger.info(f"✅ GPT-OSS client initialized - Model: {self.model}")

    async def call(self, prompt: str, temperature: float = 0.1, max_tokens: int = 500) -> str:
        try:
            logger.info(f"🟡 GPT-OSS call - model: {self.model}")

            message = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            response = message.choices[0].message.content
            logger.info(f"✅ GPT-OSS response received ({len(response)} chars)")
            return response.strip()

        except Exception as e:
            logger.error(f"❌ GPT-OSS API error: {str(e)}")
            raise Exception(f"GPT-OSS API failed: {str(e)}")

# ============================================================================
# INTENT ANALYZER - Enhanced with context awareness
# ============================================================================

class IntentAnalyzer:
    """Layer 1: Analyze user intent using Qwen with conversation context"""

    def __init__(self):
        self.qwen = QwenClient()

    async def analyze(self, message: str, conversation_history: List[Dict] = None) -> dict:
            """
            Analyze user intent with conversation context.
            Returns: dict with structured intent information
            """
            try:
                context_info = ""
                if conversation_history and len(conversation_history) > 0:
                    last_exchange = conversation_history[-1]
                    context_info = f"""
    Previous conversation:
    User asked: {last_exchange.get('user', '')}
    Bot responded about: {last_exchange.get('intent', '')}
    """

                prompt = f"""Analyze this user message and determine the intent and entities.
                
                IMPORTANT: Return ONLY a valid JSON object. Do not include any thinking process, 
explanations, markdown formatting, or text outside the JSON.

Required JSON format:
{{"primary_intent": "...", "entity_type": "...", "requires_aggregation": true/false, "confidence": 0.0-1.0}}

    {context_info}

    Current message: {message}

    Return ONLY a JSON object (no markdown, no explanation):

    {{
    "primary_intent": "one of: query, aggregate, count, list, filter",
    "entity_type": "one of: invoice, vendor, user, po, department",
    "requires_aggregation": true/false,
    "confidence": 0.0-1.0
    }}

    Examples:
    - "total amount paid to Google" → {{"primary_intent": "aggregate", "entity_type": "vendor", "requires_aggregation": true}}
    - "pending invoices" → {{"primary_intent": "filter", "entity_type": "invoice", "requires_aggregation": false}}
    - "how many invoices this month" → {{"primary_intent": "count", "entity_type": "invoice"}}

    JSON output:"""

                response = await self.qwen.call(prompt, temperature=0.2, max_tokens=200)
                
                # Clean response
                response = response.strip()
                response = re.sub(r'```json|```', '', response)
                
                # Parse JSON
                try:
                    intent_json = json.loads(response)
                    
                    # Validate required fields
                    if 'primary_intent' not in intent_json:
                        intent_json['primary_intent'] = 'query'
                    if 'entity_type' not in intent_json:
                        intent_json['entity_type'] = 'invoice'
                    if 'requires_aggregation' not in intent_json:
                        intent_json['requires_aggregation'] = False
                        
                    logger.info(f"✅ Intent identified: {intent_json}")
                    return intent_json
                    
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse intent JSON: {response}")
                    return {
                        "primary_intent": "query",
                        "entity_type": "invoice",
                        "requires_aggregation": False,
                        "confidence": 0.3
                    }

            except Exception as e:
                logger.error(f"Intent analysis failed: {str(e)}")
                return {
                    "primary_intent": "query",
                    "entity_type": "invoice",
                    "requires_aggregation": False,
                    "confidence": 0.0
                }

# ============================================================================
# ENHANCED MYSQL EXAMPLES WITH UNION TEMPLATES
# ============================================================================

MYSQL_UNION_TEMPLATES = """
==============================================================================
UNION QUERY TEMPLATES - USE THESE EXACT PATTERNS
==============================================================================

Template 1: INVOICES ONLY (Recommended default)
---------------------------------------------------
SELECT 
    i.invoice_number,
    i.invoice_date,
    i.total_amount,
    i.invoice_cleared,
    v.vendor_name,
    v.shortforms_of_vendors
FROM invoices i
JOIN vendors v ON i.vendor = v.vendor_name
WHERE (
    UPPER(v.vendor_name) LIKE UPPER('%KEYWORD%')
    OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%KEYWORD%')
)
ORDER BY i.invoice_date DESC
LIMIT 100;

Template 2: PURCHASE ORDERS ONLY
---------------------------------------------------
SELECT 
    po.po_number,
    po.po_date,
    po.grand_total,
    v.vendor_name,
    v.shortforms_of_vendors
FROM purchase_orders po
LEFT JOIN vendors v ON po.vendor_id = v.id
WHERE (
    UPPER(v.vendor_name) LIKE UPPER('%KEYWORD%')
    OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%KEYWORD%')
)
ORDER BY po.po_date DESC
LIMIT 100;

Template 3: UNION (Only when user EXPLICITLY requests both)
---------------------------------------------------
SELECT 
    'Invoice' AS record_type,
    i.invoice_number AS reference_number,
    DATE_FORMAT(i.invoice_date, '%Y-%m-%d') AS record_date,
    i.total_amount AS amount,
    v.vendor_name,
    v.shortforms_of_vendors
FROM invoices i
JOIN vendors v ON i.vendor = v.vendor_name
WHERE (
    UPPER(v.vendor_name) LIKE UPPER('%KEYWORD%')
    OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%KEYWORD%')
)

UNION ALL

SELECT 
    'PO' AS record_type,
    po.po_number AS reference_number,
    DATE_FORMAT(po.po_date, '%Y-%m-%d') AS record_date,
    po.grand_total AS amount,
    v.vendor_name,
    v.shortforms_of_vendors
FROM purchase_orders po
LEFT JOIN vendors v ON po.vendor_id = v.id
WHERE (
    UPPER(v.vendor_name) LIKE UPPER('%KEYWORD%')
    OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%KEYWORD%')
)

ORDER BY record_date DESC
LIMIT 100;

CRITICAL RULES:
1. DEFAULT to Template 1 (invoices only) for 90% of queries
2. Use Template 2 only when user specifically asks about "purchase orders" or "POs" ALONE
3. Use Template 3 ONLY when user explicitly says "both invoices AND purchase orders"
4. NEVER mix templates - pick ONE and use it completely
5. Replace KEYWORD with the actual search term from user message
"""
#=================================================================
# Add this NEW constant right after MYSQL_UNION_TEMPLATES
#=================================================================

SIMPLIFIED_SQL_PROMPT = """You are a MySQL query generator for an invoice management system.

DATABASE SCHEMA:
{schema}

MANDATORY RULES:
1. Generate ONLY SELECT queries (no INSERT/UPDATE/DELETE)
2. Output ONLY raw SQL - NO markdown (```sql), NO explanations, NO comments
3. Always end with LIMIT 100
4. Use MySQL syntax: CURDATE(), DATE_SUB(), UPPER(), LIKE

VENDOR MATCHING (CRITICAL):
When filtering by vendor name, ALWAYS use this exact pattern:
```
FROM invoices i
JOIN vendors v ON i.vendor = v.vendor_name
WHERE (
    UPPER(v.vendor_name) LIKE UPPER('%keyword%')
    OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%keyword%')
)
```

QUERY TYPE: {query_type}

{examples}

USER QUESTION: "{message}"
{vendor_hint}

Generate SQL now (output ONLY the SELECT statement):
"""

QUERY_TYPE_EXAMPLES = {
    "created_by_user": """
EXAMPLE FOR 'CREATED BY' QUERIES:
SELECT i.invoice_number, i.invoice_date, i.vendor, i.total_amount, 
       i.invoice_cleared, i.created_by
FROM invoices i
WHERE UPPER(i.created_by) LIKE UPPER('%mrunal%')
ORDER BY i.invoice_date DESC
LIMIT 100;
""",

 "approved_by_user": """
EXAMPLE FOR 'APPROVED BY' QUERIES:
SELECT i.invoice_number, i.invoice_date, i.vendor, i.total_amount, 
       i.invoice_cleared, i.approved_by, i.created_by
FROM invoices i
WHERE UPPER(i.approved_by) LIKE UPPER('%abhilash%')
ORDER BY i.invoice_date DESC
LIMIT 100;
""",

    "invoice_only": """
EXAMPLE FOR INVOICE QUERIES:
SELECT i.invoice_number, i.invoice_date, i.total_amount, i.invoice_cleared, v.vendor_name
FROM invoices i
JOIN vendors v ON i.vendor = v.vendor_name
WHERE (UPPER(v.vendor_name) LIKE UPPER('%google%') 
       OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%google%'))
ORDER BY i.invoice_date DESC
LIMIT 100;
""",
    
    "po_only": """
EXAMPLE FOR PURCHASE ORDER QUERIES:
SELECT po.po_number, po.po_date, po.grand_total, v.vendor_name
FROM purchase_orders po
LEFT JOIN vendors v ON po.vendor_id = v.id
WHERE (UPPER(v.vendor_name) LIKE UPPER('%google%') 
       OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%google%'))
ORDER BY po.po_date DESC
LIMIT 100;
""",
    
    "both": """
EXAMPLE FOR COMBINED QUERIES (UNION):
SELECT 'Invoice' AS type, i.invoice_number AS ref, i.invoice_date AS date, 
       i.total_amount AS amount, v.vendor_name
FROM invoices i
JOIN vendors v ON i.vendor = v.vendor_name
WHERE (UPPER(v.vendor_name) LIKE UPPER('%google%') 
       OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%google%'))
UNION ALL
SELECT 'PO' AS type, po.po_number AS ref, po.po_date AS date, 
       po.grand_total AS amount, v.vendor_name
FROM purchase_orders po
LEFT JOIN vendors v ON po.vendor_id = v.id
WHERE (UPPER(v.vendor_name) LIKE UPPER('%google%') 
       OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%google%'))
ORDER BY date DESC
LIMIT 100;
"""
}

# ============================================================================
# SQL GENERATOR - Enhanced with matching and context
# ============================================================================

class SQLGenerator:
    """Layer 2: Generate SQL using GPT-OSS with vendor matching"""
    """Enhanced SQL Generator with Financial Year Support"""

    def __init__(self):
        model_name = os.getenv("SQL_MODEL_NAME", "gpt-oss-120b")
        self.gptoss = GPTOSSClient(model_name)
        self.validator = SQLValidator()
        self.fy_helper = FinancialYearHelper()

    def _detect_query_intent(self, message: str, invoice_number: str = None) -> str:
            """Enhanced query type detection with invoice-specific and count queries"""
            message_lower = message.lower()

            # Vendor-specific queries (NEW - check first!)
            vendor_query_patterns = [
                'list all vendors', 'show all vendors', 'all vendors',
                'list vendors', 'show vendors', 'vendor list',
                'count of vendors', 'how many vendors', 'number of vendors',
                'total vendors', 'vendors in system'
            ]
            if any(phrase in message_lower for phrase in vendor_query_patterns):
                if any(word in message_lower for word in ['count', 'how many', 'number of', 'total']):
                    logger.info("📋 Detected vendor count query")
                    return "vendor_count"
                else:
                    logger.info("📋 Detected vendor list query")
                    return "vendor_list"
            
            # Invoice-specific queries (NEW)
            if invoice_number:
                if any(word in message_lower for word in ['approved', 'approver', 'who approved']):
                    logger.info("📋 Detected invoice approval check query")
                    return "invoice_approval_check"
                elif any(word in message_lower for word in ['cleared', 'paid', 'status', 'payment']):
                    logger.info("📋 Detected invoice status check query")
                    return "invoice_status_check"
                elif any(word in message_lower for word in ['details', 'info', 'information', 'show']):
                    logger.info("📋 Detected invoice details query")
                    return "invoice_details"
                else:
                    logger.info("📋 Detected invoice lookup query")
                    return "invoice_lookup"
            
            # Count queries (NEW - for "how many")
            if any(phrase in message_lower for phrase in ['how many', 'count', 'number of']):
                if any(phrase in message_lower for phrase in ['processed by', 'created by', 'submitted by']):
                    logger.info("📋 Detected count by user query")
                    return "count_by_user"
                elif any(phrase in message_lower for phrase in ['approved by']):
                    logger.info("📋 Detected count approved by user query")
                    return "count_approved_by_user"
                else:
                    logger.info("📋 Detected count invoices query")
                    return "count_invoices"
            
            # User/action queries
            if any(phrase in message_lower for phrase in ['created by', 'submitted by', 'invoices by', 'processed by']):
                logger.info("📋 Detected created by user query")
                return "created_by_user"
            
            if any(phrase in message_lower for phrase in ['approved by', 'approver']):
                logger.info("📋 Detected approved by user query")
                return "approved_by_user"
            
            # UNION queries (both invoices and POs)
            if any(phrase in message_lower for phrase in [
                'both invoices and po', 'invoices and purchase orders',
                'everything for', 'all records for', 'all transactions',
                'invoices and pos', 'complete history'
            ]):
                logger.info("📋 Detected UNION query (both invoices and POs)")
                return "both"
            
            # PO-only queries
            if any(phrase in message_lower for phrase in [
                'only po', 'only purchase order', 'just po', 
                'last po', 'latest po', 'recent po', 'po for'
            ]) and 'invoice' not in message_lower:
                logger.info("📋 Detected PO-only query")
                return "po_only"
            
            # Default: invoice query
            logger.info("📋 Detected invoice query")
            return "invoice_only"
    
    # =========================================================================
    # SQL BUILDERS WITH FY FILTER
    # =========================================================================
    
    def _build_query_with_fy_filter(self, query_type: str, vendor_keyword: str, message: str) -> str:
        """
        Build SQL query with automatic financial year filtering
        """
        use_vendor_filter = bool(vendor_keyword and len(vendor_keyword) >= 2)
        
        safe_keyword = vendor_keyword.replace("'", "''")
        if use_vendor_filter:
            where_clause = f"""
        WHERE (
            UPPER(v.vendor_name) LIKE UPPER('%{safe_keyword}%')
            OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%{safe_keyword}%')
        )
        """
        else:
            where_clause = "WHERE 1=1"
                
        # Get FY filter (empty string if date already mentioned)
        fy_filter = self.fy_helper.get_fy_filter(message)
        fy_start, fy_end = self.fy_helper.get_current_fy_dates()

        message_lower = message.lower()
        status_filter = ""
        
        if any(word in message_lower for word in ['pending', 'uncleared', 'outstanding', 'unpaid']):
            status_filter = "AND i.invoice_cleared = 'No'"
            logger.info("🔍 Detected PENDING status filter")
        elif any(word in message_lower for word in ['cleared', 'paid', 'completed']):
            status_filter = "AND i.invoice_cleared = 'Yes'"
            logger.info("🔍 Detected CLEARED status filter")
        
        if query_type == "created_by_user":
            sql = f"""SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.invoice_cleared,
    i.created_by,
    i.date_submission
FROM invoices i
WHERE UPPER(i.created_by) LIKE UPPER('%{safe_keyword}%')
  {fy_filter}
  {status_filter}
ORDER BY i.invoice_date DESC
LIMIT 100;"""
        
        elif query_type == "approved_by_user":
            sql = f"""SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.invoice_cleared,
    i.approved_by,
    i.created_by,
    i.date_submission
FROM invoices i
WHERE UPPER(i.approved_by) LIKE UPPER('%{safe_keyword}%')
  {fy_filter}
  {status_filter}
ORDER BY i.invoice_date DESC
LIMIT 100;"""
            if use_vendor_filter:
                where_clause = f"""
            WHERE (
                UPPER(v.vendor_name) LIKE UPPER('%{safe_keyword}%')
                OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%{safe_keyword}%')
            )
            """
            else:
                where_clause = "WHERE 1=1"

        elif query_type == "invoice_only":
            sql = f"""SELECT 
    i.invoice_number,
    i.invoice_date,
    i.total_amount,
    i.invoice_cleared,
    i.date_submission,
    v.vendor_name,
    v.shortforms_of_vendors
FROM invoices i
JOIN vendors v ON i.vendor = v.vendor_name
{where_clause}
  {fy_filter}
  {status_filter}
ORDER BY i.invoice_date DESC
LIMIT 100;"""
        
        elif query_type == "po_only":
            if 'last' in safe_keyword.lower():
                sql = f"""SELECT 
    po.po_number,
    po.po_date,
    po.grand_total,
    v.vendor_name,
    po.created_at
FROM purchase_orders po
LEFT JOIN vendors v ON po.vendor_id = v.id
ORDER BY po.created_at DESC
LIMIT 1;"""
            else:
                sql = f"""SELECT 
    po.po_number,
    po.po_date,
    po.grand_total,
    v.vendor_name,
    v.shortforms_of_vendors
FROM purchase_orders po
LEFT JOIN vendors v ON po.vendor_id = v.id
{where_clause}
  {fy_filter.replace('i.invoice_date', 'po.po_date')}
  {status_filter}
ORDER BY po.po_date DESC
LIMIT 100;"""
        
        elif query_type == "both":
            sql = f"""SELECT 
    'Invoice' AS record_type,
    i.invoice_number AS reference_number,
    DATE_FORMAT(i.invoice_date, '%Y-%m-%d') AS record_date,
    i.total_amount AS amount,
    i.invoice_cleared AS status,
    v.vendor_name
FROM invoices i
JOIN vendors v ON i.vendor = v.vendor_name
WHERE (
    UPPER(v.vendor_name) LIKE UPPER('%{safe_keyword}%')
    OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%{safe_keyword}%')
)
  {fy_filter}
  {status_filter}

UNION ALL

SELECT 
    'PO' AS record_type,
    po.po_number AS reference_number,
    DATE_FORMAT(po.po_date, '%Y-%m-%d') AS record_date,
    po.grand_total AS amount,
    NULL AS status,
    v.vendor_name
FROM purchase_orders po
LEFT JOIN vendors v ON po.vendor_id = v.id
WHERE (
    UPPER(v.vendor_name) LIKE UPPER('%{safe_keyword}%')
    OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%{safe_keyword}%')
)
  {fy_filter.replace('i.invoice_date', 'po.po_date')}

ORDER BY record_date DESC
LIMIT 100;"""
        
        else:
            raise ValueError(f"Unknown query type: {query_type}")
        
        return sql
        
    def _extract_vendor_keywords(self, message: str, vendor_list: List[Dict] = None) -> List[str]:
        """
        Extract potential vendor keywords from user message - IMPROVED
        """
        if not vendor_list:
            return []
        
        keywords = []
        message_lower = message.lower()
        
        # Strategy 1: Common query patterns
        patterns = [
            r'about\s+(\w+)',
            r'for\s+(\w+)',
            r'from\s+(\w+)',
            r'of\s+(\w+)',
            r'vendor\s+(\w+)',
            r'company\s+(\w+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, message_lower)
            keywords.extend(matches)
        
        # Strategy 2: Match against actual vendor list (most reliable)
        words = re.findall(r'\b\w{3,}\b', message_lower)  # Only words 3+ chars
        
        for word in words:
            for vendor in vendor_list:
                vendor_name = vendor.get('vendor_name', '').lower()
                shortform = vendor.get('shortforms_of_vendors', '').lower()
                
                # Check if word is part of vendor name or exact shortform match
                if word in shortform.split() or word in vendor_name.split():
                    keywords.append(word)
                    logger.info(f"✅ Matched '{word}' to vendor: {vendor.get('vendor_name', '')}")
                    break
        
        # Strategy 3: Check for partial matches in vendor names
        if not keywords:
            for vendor in vendor_list:
                vendor_name = vendor.get('vendor_name', '').lower()
                shortform = vendor.get('shortforms_of_vendors', '').lower()
                
                # Find any word from message that appears in vendor name
                for word in words:
                    if len(word) > 3 and (word in vendor_name or word in shortform):
                        keywords.append(word)
                        logger.info(f"✅ Partial match '{word}' in vendor: {vendor.get('vendor_name', '')}")
                        break
        
        # Remove duplicates and stop words
        stop_words = {
            'tell', 'about', 'show', 'get', 'find', 'list', 'the', 'me', 
            'invoices', 'invoice', 'purchase', 'orders', 'order', 'po', 'pos',
            'for', 'from', 'with', 'vendor', 'company', 'details', 'total',
            'pending', 'approved', 'cleared', 'last', 'latest', 'recent',
            'give', 'what', 'which', 'how', 'many', 'much', 'all'
        }
        keywords = list(set([k for k in keywords if k not in stop_words]))
        
        logger.info(f"📝 Extracted vendor keywords: {keywords[:3]}")
        return keywords[:3]  # Return top 3
    
    def _extract_invoice_number(self, message: str) -> Optional[str]:
        """
        Extract invoice number from user message.
        Handles formats: INV-123, INV123, invoice: INV-123, etc.
        """
        patterns = [
            r'invoice[:\s#]+([A-Z0-9\-/]+)',   # "invoice: INV-123" or "invoice #INV-123"
            r'inv[:\s#]+([A-Z0-9\-/]+)',        # "inv: INV-123"
            r'\b([A-Z]{2,5}\-\d{2,6})\b',       # "INV-123", "BILL-2024"
            r'\b([A-Z]{2,5}\d{2,6})\b',         # "INV123", "BILL2024"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                invoice_num = match.group(1).upper()
                logger.info(f"📋 Extracted invoice number: {invoice_num}")
                return invoice_num
        
        return None
    
    def _extract_username(self, message: str) -> Optional[str]:
        """Extract username from queries like 'approved by John' or 'invoices by Sarah'"""
        patterns = [
            r'(?:by|from)\s+(\w+)',           # "by John" or "from Sarah"
            r'user\s+(\w+)',                   # "user John"
            r'approver\s+(\w+)',               # "approver John"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message.lower())
            if match:
                username = match.group(1)
                logger.info(f"👤 Extracted username: {username}")
                return username
        
        return None
    
    def _build_query_from_template(self, query_type: str, vendor_keyword: str) -> str:
        """Build SQL query using predefined templates"""
    
        # ADD THIS VALIDATION CHECK AT THE START
        if not vendor_keyword or len(vendor_keyword) < 2:
            logger.warning(f"⚠️ Invalid vendor keyword: '{vendor_keyword}', using fallback")
            vendor_keyword = "google"  # Safe fallback
        
        # Escape the keyword for SQL LIKE
            safe_keyword = vendor_keyword.replace("'", "''")
            
            logger.info(f"🎯 Building {query_type} query for keyword: {safe_keyword}")
            
            # NEW: Created by user query
            if query_type == "created_by_user":
                sql = f"""SELECT 
            i.invoice_number,
            i.invoice_date,
            i.vendor,
            i.total_amount,
            i.invoice_cleared,
            i.created_by,
            i.date_submission
        FROM invoices i
        WHERE UPPER(i.created_by) LIKE UPPER('%{safe_keyword}%')
        ORDER BY i.invoice_date DESC
        LIMIT 100;"""
                return sql
            
            if query_type == "approved_by_user":
                sql = f"""SELECT 
            i.invoice_number,
            i.invoice_date,
            i.vendor,
            i.total_amount,
            i.invoice_cleared,
            i.approved_by,
            i.created_by,
            i.date_submission
        FROM invoices i
        WHERE UPPER(i.approved_by) LIKE UPPER('%{safe_keyword}%')
        ORDER BY i.invoice_date DESC
        LIMIT 100;"""
                
            elif query_type == "count_by_user":
                # Count invoices by specific user
                sql = f"""SELECT 
            COUNT(*) AS invoice_count,
            SUM(i.total_amount) AS total_amount,
            i.created_by
        FROM invoices i
        WHERE UPPER(i.created_by) LIKE UPPER('%{safe_keyword}%')
        {fy_filter}
        {status_filter}
        GROUP BY i.created_by;"""
            
            elif query_type == "count_approved_by_user":
                # Count invoices approved by specific user
                sql = f"""SELECT 
            COUNT(*) AS invoice_count,
            SUM(i.total_amount) AS total_amount,
            i.approved_by
        FROM invoices i
        WHERE UPPER(i.approved_by) LIKE UPPER('%{safe_keyword}%')
        {fy_filter}
        {status_filter}
        GROUP BY i.approved_by;"""
            
            elif query_type in ["invoice_approval_check", "invoice_status_check", "invoice_details", "invoice_lookup"]:
                # Invoice-specific lookup
                sql = f"""SELECT 
            i.invoice_number,
            i.invoice_date,
            i.vendor,
            i.total_amount,
            i.invoice_cleared,
            i.invoice_cleared_date,
            i.created_by,
            i.approved_by,
            i.reviewed_by,
            i.date_submission,
            v.vendor_name,
            v.shortforms_of_vendors
        FROM invoices i
        JOIN vendors v ON i.vendor = v.vendor_name
        WHERE i.invoice_number = '{safe_keyword}'
        LIMIT 1;"""
        
        if not vendor_keyword:
            vendor_keyword = "google"  # Safe fallback
        
        # Escape the keyword for SQL LIKE
        safe_keyword = vendor_keyword.replace("'", "''")
        
        if query_type == "invoice_only":
            sql = f"""SELECT 
    i.invoice_number,
    i.invoice_date,
    i.total_amount,
    i.invoice_cleared,
    i.date_submission,
    v.vendor_name,
    v.shortforms_of_vendors
FROM invoices i
JOIN vendors v ON i.vendor = v.vendor_name
WHERE (
    UPPER(v.vendor_name) LIKE UPPER('%{safe_keyword}%')
    OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%{safe_keyword}%')
    OR UPPER(i.created_by) LIKE UPPER('%{safe_keyword}%')
)
ORDER BY i.invoice_date DESC
LIMIT 100;"""
        
        elif query_type == "po_only":
    # Check if asking for "last PO" specifically
            if 'last' in safe_keyword.lower() or not safe_keyword or safe_keyword == 'google':
                sql = f"""SELECT 
            po.po_number,
            po.po_date,
            po.grand_total,
            v.vendor_name,
            po.created_at
        FROM purchase_orders po
        LEFT JOIN vendors v ON po.vendor_id = v.id
        ORDER BY po.created_at DESC
        LIMIT 1;"""
            else:
                sql = f"""SELECT 
            po.po_number,
            po.po_date,
            po.grand_total,
            v.vendor_name,
            v.shortforms_of_vendors
        FROM purchase_orders po
        LEFT JOIN vendors v ON po.vendor_id = v.id
        WHERE (
            UPPER(v.vendor_name) LIKE UPPER('%{safe_keyword}%')
            OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%{safe_keyword}%')
        )
        ORDER BY po.po_date DESC
        LIMIT 100;"""
        
        elif query_type == "both":
            sql = f"""SELECT 
    'Invoice' AS record_type,
    i.invoice_number AS reference_number,
    DATE_FORMAT(i.invoice_date, '%Y-%m-%d') AS record_date,
    i.total_amount AS amount,
    i.invoice_cleared AS status,
    v.vendor_name,
    v.shortforms_of_vendors
FROM invoices i
JOIN vendors v ON i.vendor = v.vendor_name
WHERE (
    UPPER(v.vendor_name) LIKE UPPER('%{safe_keyword}%')
    OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%{safe_keyword}%')
)

UNION ALL

SELECT 
    'PO' AS record_type,
    po.po_number AS reference_number,
    DATE_FORMAT(po.po_date, '%Y-%m-%d') AS record_date,
    po.grand_total AS amount,
    NULL AS status,
    v.vendor_name,
    v.shortforms_of_vendors
FROM purchase_orders po
LEFT JOIN vendors v ON po.vendor_id = v.id
WHERE (
    UPPER(v.vendor_name) LIKE UPPER('%{safe_keyword}%')
    OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%{safe_keyword}%')
)

ORDER BY record_date DESC
LIMIT 100;"""
        
        else:
            raise ValueError(f"Unknown query type: {query_type}")
        
        return sql

    async def generate(
            self, 
            message: str, 
            intent: str, 
            schema: str, 
            conversation_history: List[Dict] = None,
            vendor_list: List[Dict] = None,
            user_list: List[Dict] = None,
            confirmed_entity: Dict = None,
            confirmed_date_range: Dict = None
        ) -> str:
        """
        SQL generation with automatic Financial Year filtering
        Uses template-based approach for common queries, LLM for complex ones
        """
         # If confirmed parameters exist, use them directly in prompt
        if confirmed_entity:
            # Add confirmed entity info to prompt
            prompt += f"\\nCONFIRMED ENTITY: {confirmed_entity['name']} (ID: {confirmed_entity['id']})"
        
        if confirmed_date_range:
            # Add confirmed date range to prompt
            prompt += f"\\nCONFIRMED DATE RANGE: {confirmed_date_range['from']} to {confirmed_date_range['to']}"
        try:
            # Sanitize user input first
            message = self.validator.sanitize_user_input(message)
            
            logger.info(f"🎯 Generating SQL for: {message[:100]}")
            # Extract invoice number if present
            invoice_number = self._extract_invoice_number(message)
            if invoice_number:
                logger.info(f"📋 Found invoice number in query: {invoice_number}")
            
            # ==================================================================
            # STEP 1: Detect query type and extract keywords
            # ==================================================================
            query_type = self._detect_query_intent(message,invoice_number)
            message_lower = message.lower()

            # ===== AGGREGATE QUERIES =====
            aggregate_keywords = ['total', 'sum', 'altogether', 'combined', 'budget', 'spent', 'consumed', 'paid']
            count_keywords = ['how many', 'count', 'number of']

            is_aggregate = any(keyword in message_lower for keyword in aggregate_keywords)
            is_count = any(keyword in message_lower for keyword in count_keywords)

            if is_aggregate or is_count:
                logger.info("📊 Detected aggregate/count query")
                
                # Get FY filter
                fy_filter = self.fy_helper.get_fy_filter(message)

                vendor_keywords = self._extract_vendor_keywords(message, vendor_list)
                
                # Detect what to aggregate
                if any(k in message_lower for k in ['pending', 'uncleared', 'outstanding', 'unpaid']):
                    # Total pending invoices
                    sql = f"""SELECT 
                COUNT(*) AS total_invoices,
                SUM(total_amount) AS total_amount
            FROM invoices i
            WHERE i.invoice_cleared = 'No'
            {fy_filter};"""
                    logger.info("✅ Generated aggregate SQL for pending invoices")
                    return sql
                
                elif any(k in message_lower for k in ['cleared', 'paid', 'completed']):
                    # Total cleared/paid invoices
                    sql = f"""SELECT 
                COUNT(*) AS total_invoices,
                SUM(total_amount) AS total_amount
            FROM invoices i
            WHERE i.invoice_cleared = 'Yes'
            {fy_filter};"""
                    logger.info("✅ Generated aggregate SQL for cleared invoices")
                    return sql
                
                elif vendor_keywords:
                    # Total for specific vendor
                    vendor_keyword = vendor_keywords[0]
                    safe_keyword = vendor_keyword.replace("'", "''")
                    
                    sql = f"""SELECT 
                v.vendor_name,
                v.shortforms_of_vendors,
                COUNT(i.id) AS invoice_count,
                SUM(i.total_amount) AS total_amount,
                SUM(CASE WHEN i.invoice_cleared = 'Yes' THEN i.total_amount ELSE 0 END) AS paid_amount,
                SUM(CASE WHEN i.invoice_cleared = 'No' THEN i.total_amount ELSE 0 END) AS pending_amount
            FROM invoices i
            JOIN vendors v ON i.vendor = v.vendor_name
            WHERE (
                UPPER(v.vendor_name) LIKE UPPER('%{safe_keyword}%')
                OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%{safe_keyword}%')
            )
            {fy_filter}
            GROUP BY v.vendor_name, v.shortforms_of_vendors;"""
                    logger.info("✅ Generated aggregate SQL for vendor")
                    return sql
                
                else:
                    # General total/budget query
                    sql = f"""SELECT 
                COUNT(*) AS total_invoices,
                SUM(total_amount) AS total_amount,
                SUM(CASE WHEN invoice_cleared = 'Yes' THEN total_amount ELSE 0 END) AS cleared_amount,
                SUM(CASE WHEN invoice_cleared = 'No' THEN total_amount ELSE 0 END) AS pending_amount
            FROM invoices i
            WHERE 1=1
            {fy_filter};"""
                    logger.info("✅ Generated aggregate SQL for general budget")
                    return sql

            vendor_keyword = vendor_keywords[0] if vendor_keywords else ""
            # Override vendor_keyword with invoice number for invoice-specific queries
            if invoice_number and query_type in ["invoice_approval_check", "invoice_status_check", "invoice_details", "invoice_lookup"]:
                vendor_keyword = invoice_number
                logger.info(f"📋 Using invoice number as search keyword: {invoice_number}")

            # Extract username for user-specific queries
            if not vendor_keyword and query_type in ["created_by_user", "approved_by_user", "count_by_user", "count_approved_by_user"]:
                username = self._extract_username(message)
                if username:
                    vendor_keyword = username
                    logger.info(f"👤 Using username as search keyword: {username}")
            
            # ==================================================================
            # STEP 2: Special handling for user-based queries
            # ==================================================================
            
            # Check for "created by" queries
            if any(phrase in message_lower for phrase in ['created by', 'submitted by', 'invoices by']):
                query_type = "created_by_user"
                # Extract username
                for pattern in [r'by\s+(\w+)', r'from\s+(\w+)']:
                    match = re.search(pattern, message_lower)
                    if match:
                        vendor_keyword = match.group(1)
                        logger.info(f"📝 Created by: {vendor_keyword}")
                        break
            
            # Check for "approved by" queries
            elif any(phrase in message_lower for phrase in ['approved by', 'approver']):
                query_type = "approved_by_user"
                # Extract username
                for pattern in [r'by\s+(\w+)', r'approver\s+(\w+)']:
                    match = re.search(pattern, message_lower)
                    if match:
                        vendor_keyword = match.group(1)
                        logger.info(f"✅ Approved by: {vendor_keyword}")
                        break
            
            logger.info(f"📋 Query type: {query_type}, Keyword: {vendor_keyword}")
            
            # ==================================================================
            # STEP 3: Try template-based generation first (WITH FY FILTER)
            # ==================================================================
            
            # Use templates for common query types
            if query_type in ["created_by_user", "approved_by_user", "invoice_only", "po_only", "both","vendor_count","vendor_list",
                              "invoice_approval_check","invoice_status_check","invoice_details","invoice_lookup",]:
                try:
                    logger.info(f"🏗️ Building from template with FY filter...")
                    sql = self._build_query_with_fy_filter(query_type, vendor_keyword, message)
                    
                    # Validate
                    sql, warnings = self.validator.validate_and_fix(sql)
                    
                    logger.info(f"✅ Template-based SQL with FY filter: {sql[:150]}...")
                    return sql
                    
                except Exception as template_error:
                    logger.warning(f"⚠️ Template generation failed: {template_error}")
                    logger.info("🔄 Falling back to LLM-based generation...")
            
            # ==================================================================
            # STEP 4: LLM-based generation for complex queries (WITH FY INFO)
            # ==================================================================
            
            # Get FY dates for prompt context
            fy_start, fy_end = self.fy_helper.get_current_fy_dates()
            fy_filter_example = self.fy_helper.get_fy_filter(message)
            
            # Build context from conversation if available
            context_info = ""
            if conversation_history and len(conversation_history) > 0:
                last = conversation_history[-1]
                previous_sql = last.get('sql', '')
                
                vendor_match = re.search(r"LIKE\s+UPPER\('%([^%]+)%'\)", previous_sql, re.IGNORECASE)
                if vendor_match:
                    previous_vendor = vendor_match.group(1)
                    context_info = f"""
    CONTEXT FROM PREVIOUS QUERY:
    - User previously asked about: "{last.get('user', '')}"
    - Query involved vendor/keyword: "{previous_vendor}"

    Use this context to better understand current query.
    """
                    
                    # ✅ BUILD VENDOR CONTEXT
            vendor_context = ""
            if vendor_list:
                vendor_samples = [
                    f"- {v['vendor_name']} (shortform: {v.get('shortforms_of_vendors', 'N/A')})" 
                    for v in vendor_list[:30]
                ]
                vendor_context = f"""
            AVAILABLE VENDORS ({len(vendor_list)} total, showing first 30):
            {chr(10).join(vendor_samples)}

            When user mentions a vendor name or shortform:
            1. Match it against this list
            2. Use the exact vendor_name in your query
            3. Use LIKE matching for flexible search: UPPER(v.vendor_name) LIKE UPPER('%keyword%')
            """

            # ✅ BUILD USER CONTEXT
            user_context = ""
            if user_list:
                user_samples = [
                    f"- {u['name']} ({u.get('email', 'N/A')}) - {u.get('role', 'User')} - {u.get('department', 'N/A')}" 
                    for u in user_list[:50]
                ]
                user_context = f"""
            AVAILABLE USERS ({len(user_list)} total, showing first 50):
            {chr(10).join(user_samples)}

            CRITICAL - USER QUERY RULES:
            1. For INVOICES: created_by/approved_by/reviewed_by are VARCHAR (text)
            - Use: WHERE UPPER(i.created_by) LIKE UPPER('%name%')
            - Example: WHERE UPPER(i.created_by) LIKE UPPER('%rahul%')

            2. For PURCHASE_ORDERS: created_by/approved_by/reviewed_by are INT (user IDs)
            - Must JOIN users table: JOIN users u ON po.created_by = u.id
            - Then filter: WHERE UPPER(u.name) LIKE UPPER('%rahul%')

            3. When user asks about a person:
            - Match their name against the user list above
            - Use partial matching (first name only is OK)
            - Handle both full names and first names

            4. NEVER mix INT and VARCHAR approaches!
            """
            
            # Enhanced prompt with FY filtering instructions
            prompt = f"""You are an expert MySQL query generator for an invoice and purchase order management system.

    DATABASE SCHEMA:
    {INVOICE_DB_SCHEMA_TEXT}

    {vendor_context}

    {user_context}

    COMPREHENSIVE EXAMPLES (study these patterns):
    {MYSQL_EXAMPLES}

    {ENHANCED_STATUS_EXAMPLES}

    {context_info}

    FINANCIAL YEAR FILTERING (CRITICAL):
    Current Financial Year: {fy_start} to {fy_end}
    - If query does NOT mention specific dates → Add: AND i.invoice_date >= '{fy_start}' AND i.invoice_date <= '{fy_end}'
    - If query mentions dates/periods → Do NOT add FY filter

    Date keywords that prevent FY filter:
    - "last month", "this month", "last week", "yesterday"
    - "2024", "2025", "2026", month names
    - "days ago", "weeks ago", "months ago"

    STATUS FILTERING (CRITICAL):
    - "pending/uncleared/outstanding" → Add: AND i.invoice_cleared = 'No'
    - "cleared/paid/completed" → Add: AND i.invoice_cleared = 'Yes'
    - If NO status keyword → Do NOT add status filter

    USER QUESTION: "{message}"

    INSTRUCTIONS:
    Identify the main entity: invoice, PO, vendor, or user and user actions.
    Follow these steps strictly:
    1. Read the user's question carefully
    2. Check if date/period is mentioned → Skip FY filter if yes
    3. If NO date mentioned → ADD FY filter automatically
    4. Map keywords to correct columns:
    - "created by X" → WHERE UPPER(created_by) LIKE UPPER('%X%')
    - "approved by X" → WHERE UPPER(approved_by) LIKE UPPER('%X%')
    - "reviewed by X" → WHERE UPPER(reviewed_by) LIKE UPPER('%X%')
    - "pending" → WHERE invoice_cleared = 'No'
    - "cleared" → WHERE invoice_cleared = 'Yes'
    - "vendor X" → JOIN vendors + WHERE vendor filter

    5. Use proper JOINs:
    - For invoices: JOIN vendors v ON i.vendor = v.vendor_name
    - For POs: LEFT JOIN vendors v ON po.vendor_id = v.id

    6. Always use UPPER() for text comparisons
    7. Always use % wildcards for partial matching
    8. Always ORDER BY relevant date DESC
    9. Always end with LIMIT 100

    EXAMPLE BREAKDOWN FOR "pending invoices for Google":
    - Entity: invoice
    - Status: "pending" → invoice_cleared = 'No'
    - Vendor: "Google" → vendor filter
    - Date: not mentioned → add FY filter
    - Final SQL:
    SELECT ... FROM invoices i
    JOIN vendors v ON i.vendor = v.vendor_name
    WHERE (vendor filter)
        AND i.invoice_cleared = 'No'
        AND i.invoice_date >= '{fy_start}' AND i.invoice_date <= '{fy_end}'

    OUTPUT REQUIREMENTS:
    - Generate ONLY the SELECT statement
    - NO markdown code blocks (no ```sql)
    - NO explanations or comments
    - Just the raw SQL query

    Generate the SQL query now:
    """
            
            # Call LLM
            logger.info("🤖 Calling LLM for SQL generation...")
            sql = await self.gptoss.call(prompt, temperature=0.05, max_tokens=800)
            
            # Clean up response
            sql = sql.strip()
            sql = re.sub(r'```sql|```', '', sql, flags=re.IGNORECASE)
            sql = re.sub(r'^.*?SELECT', 'SELECT', sql, flags=re.IGNORECASE | re.DOTALL)
            
            if ';' in sql:
                sql = sql[:sql.rfind(';') + 1]
            
            sql = sql.strip()
            
            # Validate
            if not sql.upper().startswith('SELECT'):
                logger.error(f"❌ Generated query doesn't start with SELECT")
                raise ValueError("Query must start with SELECT")
            
            # ==================================================================
            # STEP 5: Post-process to ensure FY filter is applied
            # ==================================================================
            
            # Check if FY filter should be applied but is missing
            if fy_filter_example and 'invoice_date >=' not in sql.lower():
                logger.warning("⚠️ LLM didn't add FY filter, adding it now...")
                
                # Find WHERE clause and insert FY filter
                if 'WHERE' in sql.upper():
                    # Insert after WHERE
                    sql = re.sub(
                        r'(WHERE\s+)',
                        r'\1' + f'i.invoice_date >= \'{fy_start}\' AND i.invoice_date <= \'{fy_end}\' AND ',
                        sql,
                        count=1,
                        flags=re.IGNORECASE
                    )
                else:
                    # No WHERE clause, add one before ORDER BY
                    sql = re.sub(
                        r'(ORDER\s+BY)',
                        f'WHERE i.invoice_date >= \'{fy_start}\' AND i.invoice_date <= \'{fy_end}\'\n\\1',
                        sql,
                        count=1,
                        flags=re.IGNORECASE
                    )
                
                logger.info(f"✅ FY filter added post-LLM generation")
            
            # Final validation
            sql, warnings = self.validator.validate_and_fix(sql)
            
            logger.info(f"✅ SQL generated: {sql[:150]}...")
            return sql
            
        except Exception as e:
            logger.error(f"❌ SQL generation failed: {e}")
            import traceback
            traceback.print_exc()
            
            # ==================================================================
            # FALLBACK with FY filter
            # ==================================================================
            logger.info("🆘 Using fallback SQL with FY filter...")
            fy_filter = self.fy_helper.get_fy_filter(message)
            
            fallback_sql = f"""SELECT 
        invoice_number, 
        invoice_date, 
        vendor, 
        total_amount, 
        invoice_cleared, 
        created_by
    FROM invoices i
    WHERE 1=1
    {fy_filter}
    ORDER BY invoice_date DESC
    LIMIT 100;"""
            
            return fallback_sql
        
    def _get_smart_fallback(self, query_type: str, vendor_keyword: str) -> str:
        """Return appropriate fallback SQL based on detected intent"""
        safe_keyword = vendor_keyword.replace("'", "''")
        
        logger.info(f"🆘 Using smart fallback for {query_type} with keyword: {safe_keyword}")
        
        templates = {
            "created_by_user": f"""SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.invoice_cleared,
    i.created_by
FROM invoices i
WHERE UPPER(i.created_by) LIKE UPPER('%{safe_keyword}%')
ORDER BY i.invoice_date DESC
LIMIT 100;""",

        "approved_by_user": f"""SELECT 
    i.invoice_number,
    i.invoice_date,
    i.vendor,
    i.total_amount,
    i.invoice_cleared,
    i.approved_by,
    i.created_by
FROM invoices i
WHERE UPPER(i.approved_by) LIKE UPPER('%{safe_keyword}%')
ORDER BY i.invoice_date DESC
LIMIT 100;""",

            "invoice_only": f"""SELECT 
        i.invoice_number,
        i.invoice_date,
        i.total_amount,
        i.invoice_cleared,
        v.vendor_name
    FROM invoices i
    JOIN vendors v ON i.vendor = v.vendor_name
    WHERE (UPPER(v.vendor_name) LIKE UPPER('%{safe_keyword}%') 
        OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%{safe_keyword}%'))
    ORDER BY i.invoice_date DESC
    LIMIT 100;""",
            
            "po_only": f"""SELECT 
        po.po_number,
        po.po_date,
        po.grand_total,
        v.vendor_name
    FROM purchase_orders po
    LEFT JOIN vendors v ON po.vendor_id = v.id
    WHERE (UPPER(v.vendor_name) LIKE UPPER('%{safe_keyword}%') 
        OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%{safe_keyword}%'))
    ORDER BY po.po_date DESC
    LIMIT 100;""",
            
            "both": f"""SELECT 
        'Invoice' AS type,
        i.invoice_number AS ref,
        DATE_FORMAT(i.invoice_date, '%Y-%m-%d') AS date,
        i.total_amount AS amount,
        v.vendor_name
    FROM invoices i
    JOIN vendors v ON i.vendor = v.vendor_name
    WHERE (UPPER(v.vendor_name) LIKE UPPER('%{safe_keyword}%') 
        OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%{safe_keyword}%'))
    UNION ALL
    SELECT 
        'PO' AS type,
        po.po_number AS ref,
        DATE_FORMAT(po.po_date, '%Y-%m-%d') AS date,
        po.grand_total AS amount,
        v.vendor_name
    FROM purchase_orders po
    LEFT JOIN vendors v ON po.vendor_id = v.id
    WHERE (UPPER(v.vendor_name) LIKE UPPER('%{safe_keyword}%') 
        OR UPPER(v.shortforms_of_vendors) LIKE UPPER('%{safe_keyword}%'))
    ORDER BY date DESC
    LIMIT 100;"""
        }
        
        return templates.get(query_type, templates["invoice_only"])
# ============================================================================
# RESPONSE FORMATTER - Enhanced with better formatting
# ============================================================================

class ResponseFormatter:
    """Layer 4: Enhanced response formatting with universal humanization"""

    def __init__(self):
        self.qwen = QwenClient()

    async def format(self, data: List[Dict], intent: str, message: str) -> str:
        """
        Universal formatter that adapts to any query type
        Returns natural, complete, humanized responses
        """
        try:
            # Handle empty results with helpful message
            if not data or len(data) == 0:
                return self._format_empty_response(message)
            
            row_count = len(data)
            
            # Detect query type for specialized handling
            query_type = self._detect_query_type(data, intent)
            
            # Get adaptive template based on result size
            template = self._get_response_template(row_count, query_type)
            
            # Prepare clean data context
            data_context = self._prepare_data_context(data, max_rows=8)
            
            # Build comprehensive prompt
            prompt = f"""You are a helpful database assistant providing query results in a natural, conversational way.

USER'S QUESTION: "{message}"

QUERY DETAILS:
- Intent: {intent}
- Query Type: {query_type}
- Total Records: {row_count}

{template}

SAMPLE DATA (first few records):
{data_context}

{self._get_special_instructions(query_type, data)}

CRITICAL REQUIREMENTS:
✓ Write MINIMUM 4-6 complete sentences (NO one-word or one-sentence answers!)
✓ Include specific numbers, dates, and amounts from the data
✓ Provide context and insights, not just raw data
✓ Format currency as ₹X,XXX.XX (Indian Rupees with proper separators)
✓ Format dates as "15 Jan 2024" (readable format)
✓ Sound natural and conversational, like a helpful colleague
✓ Be complete and informative
✓ USE BULLET POINTS when presenting multiple items, statistics, or breakdowns
✓ Start with 1-2 sentences summary, THEN use bullets for details

STRICTLY AVOID:
✗ One-word answers like "125" or "146"
✗ One-sentence answers without details
✗ Robotic phrases like "Here is the data" or "Query successful"
✗ Just stating numbers without explanation
✗ Asking unnecessary follow-up questions
✗ Using <think> tags or any XML-like reasoning tags
✗ Meta-commentary about how you're formatting the response
✗ Long paragraphs without structure - break information into digestible bullets

Your response must be ONLY the final answer to the user - no thinking process, no reasoning tags.

Create a natural, complete, and helpful response:"""

            # Generate response with appropriate parameters
            response = await self.qwen.call(
                prompt, 
                temperature=0.6,  # Balanced creativity for natural language
                max_tokens=1200   # Allow comprehensive responses
            )
            
            response = response.strip()

            response = self._clean_response(response)

            if not response:
                logger.warning("⚠️ Response empty after cleaning, using fallback")
                return self._fallback_response(data, message)
                
            # Quality validation - ensure response is substantial
            word_count = len(response.split())
            if word_count < 15 and row_count > 0:
                logger.warning(f"⚠️ Response too short ({word_count} words), regenerating...")
                response = await self._regenerate_response(prompt, data, message)
            
            logger.info(f"✅ Response formatted: {len(response)} chars, {word_count} words")
            return response
            
        except Exception as e:
            logger.error(f"❌ Response formatting failed: {str(e)}")
            return self._fallback_response(data, message)

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _detect_query_type(self, data: List[Dict], intent: str) -> str:
        """Detect query type for specialized formatting"""
        if not data:
            return "empty"
        
        first_row = data[0]
        keys = set(first_row.keys())
        keys_lower = {k.lower() for k in keys}

        user_field_indicators = ['created_by', 'approved_by', 'reviewed_by']
        has_user_fields = any(field in keys_lower for field in user_field_indicators)

        if has_user_fields:
            # If we have user fields AND the data emphasizes them, it's a user query
            if intent == "user" or "user" in str(intent).lower():
                logger.info("🧑 Detected user_query type")
                return "user_query"
            
            # Check if created_by/approved_by/reviewed_by has actual values (not NULL)
            for field in user_field_indicators:
                if field in keys_lower:
                    field_value = first_row.get(field) or first_row.get(field.upper())
                    if field_value and str(field_value).strip() and str(field_value) != 'None':
                        logger.info("🧑 Detected user_query type (has user field values)")
                        return "user_query"
        
        # Also check if we're querying the users table directly
        if any(k in keys_lower for k in ['email', 'role', 'is_active', 'department']):
            # Likely a direct users table query
            logger.info("🧑 Detected user_query type (users table)")
            return "user_query"
    
        
        # Aggregate query (has SUM, COUNT, AVG, etc.)
        aggregate_keywords = ['total', 'sum', 'count', 'avg', 'average', 
                             'total_amount', 'total_pending', 'grand_total']
        if any(keyword in keys_lower for keyword in aggregate_keywords):
            return "aggregate"
        
        # Vendor-specific query
        if any(k in keys_lower for k in ['vendor_name', 'vendor', 'shortforms_of_vendors']):
            return "vendor_query"
        
        # Invoice listing
        if any(k in keys_lower for k in ['invoice_number', 'invoice_amount', 'invoice_date']):
            return "invoice_list"
        
        # Purchase Order query
        if 'po_number' in keys_lower:
            return "purchase_order"
        
        # Status/filter query
        if intent in ['filter', 'list'] and len(data) > 1:
            return "filtered_list"
        
        return "general"

    def _get_response_template(self, row_count: int, query_type: str) -> str:
        """Get adaptive response template based on result size and type"""
        
        # Single result responses
        if row_count == 1:
            return """
SINGLE RESULT FORMAT:
• Start with a brief intro sentence
• Present key details in 3-5 bullet points
• Each bullet should be complete and informative
• End with a natural closing sentence

Example: "I found the invoice you're looking for:
• Invoice #INV-2024-001 from NCS Corporation
• Date: 15 Jan 2024
• Amount: ₹45,230.50
• Status: Pending approval
This invoice is currently awaiting processing in the approval queue."
"""
        
        # Small dataset (2-10 results)
        elif row_count <= 10:
            return """
SMALL DATASET FORMAT:
• Start with 1-2 sentence summary with total count and key metric
• Use bullet points to list individual items or grouped categories
• Include specific details: dates, amounts, vendors
• Add a summary statistic at the end (total, average, etc.)

Example: "I found 5 pending invoices from NCS totaling ₹2,15,450.00:
• INV-2024-015 (20 Jan) - ₹75,000.00
• INV-2024-012 (18 Jan) - ₹52,450.00
• INV-2024-009 (15 Jan) - ₹38,000.00
• INV-2024-006 (12 Jan) - ₹30,000.00
• INV-2024-003 (10 Jan) - ₹20,000.00
All invoices are currently in the approval workflow and pending final clearance."
"""
        
        # Medium dataset (11-50 results)
        elif row_count <= 50:
            return """
MEDIUM DATASET FORMAT:
• Opening: 1-2 sentences with total count, amount, and date range
• Key Statistics section with 3-5 bullets showing aggregates/distributions
• Highlights section with top 3-5 items
• Closing sentence with actionable insight

Example: "I found 28 invoices pending approval, totaling ₹8,45,230.00 from Nov-Dec 2025.

Key Statistics:
• Total Amount: ₹8,45,230.00 across 12 vendors
• Average Invoice: ₹30,186.79
• Date Range: 5 Nov 2025 to 18 Dec 2025
• Departments: Marketing (15), Operations (8), IT (5)

Top Invoices:
• ABC Corp - ₹1,50,000 (Largest pending)
• XYZ Ltd - ₹95,000
• NCS - ₹78,500

Most invoices are awaiting HOD approval and should be prioritized for processing."
"""
        
        # Large dataset (50+ results)
        else:
            return """
LARGE DATASET FORMAT:
• Executive Summary: 1-2 sentences with headline numbers
• Overview section with 4-6 key statistics as bullets
• Breakdown section by category (vendors, departments, status, etc.)
• Top Items section with 3 highlights
• Closing insight or recommendation

Example: "I found 156 invoices across 45 vendors, totaling ₹45,67,890.00 from the last quarter.

Overview:
• Total Records: 156 invoices
• Total Value: ₹45,67,890.00
• Date Range: Oct 2025 - Dec 2025
• Average Invoice: ₹29,281.98
• Active Vendors: 45

Breakdown by Status:
• Pending: 89 invoices (₹28,45,670) - 57%
• Approved: 52 invoices (₹14,32,110) - 33%
• Cleared: 15 invoices (₹2,90,110) - 10%

Top 3 Vendors:
• NCS - ₹12,50,000 (27%)
• ABC Corp - ₹8,20,000 (18%)
• XYZ Ltd - ₹6,15,000 (13%)

The pending invoices represent a significant backlog that requires attention to maintain healthy vendor relationships."
"""


    def _clean_response(self, response: str) -> str:
        """Remove thinking tags and unwanted content from LLM response"""
        import re
        
        # Remove <think>...</think> tags and their content
        response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove any other XML-like thinking tags
        response = re.sub(r'</?think>', '', response, flags=re.IGNORECASE)

        # Extract JSON object if there's extra text
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response)
        if json_match:
            response = json_match.group(0)
        
        # Remove leading/trailing whitespace
        response = response.strip()
        
        # Remove multiple consecutive newlines
        response = re.sub(r'\n{3,}', '\n\n', response)
        
        # If response is now empty, return a fallback
        if not response or len(response.strip()) < 10:
            logger.warning("⚠️ Response became empty after cleaning thinking tags")
            return None
        
        return response
    
    def _get_special_instructions(self, query_type: str, data: List[Dict]) -> str:
        """Get specialized formatting instructions based on query type"""
        
        instructions = {
            "aggregate": """
AGGREGATE QUERY SPECIAL INSTRUCTIONS:
• Start with 1 sentence stating the main result
• Break down the number with context using bullets:
  - Total amount/count
  - Time period or scope
  - Number of entities (vendors, departments, etc.)
  - Any notable patterns
• End with brief insight or context

Example: "The total pending invoice amount is ₹8,45,230.50:
• Amount: ₹8,45,230.50
• Vendors: 23 different vendors
• Time Period: Most invoices from last 30 days
• Status: All awaiting approval or payment
This represents the current outstanding obligations that need processing."
""",

"user_query": """
USER QUERY SPECIAL INSTRUCTIONS:
- Start with the user's full name, role, and department if available
- Break down their activity by type (created, approved, reviewed)
- Include time-based metrics (this month, this year, all time)
- Show vendor diversity if relevant
- Use clear sections with bullet points
- End with an insight or summary

Example Response Format:
"Rahul Kumar (HOD - Finance Department) has been actively processing invoices:

Activity Summary:
- Created: 45 invoices totaling ₹12,34,500
- Approved: 23 invoices totaling ₹8,45,200
- Reviewed: 12 invoices totaling ₹3,21,000

This Month's Activity (January 2025):
- 8 invoices created (₹2,45,000)
- 5 invoices approved (₹1,89,000)
- Average processing time: 2.3 days

Top Vendors Processed:
- ABC Corp - 15 invoices
- XYZ Ltd - 12 invoices  
- NCS - 8 invoices

Status Breakdown:
- Cleared: 60 invoices (₹15,23,400)
- Pending: 20 invoices (₹5,54,300)

Rahul is one of the most active users in the Finance department with consistent invoice processing throughout the month."

IMPORTANT:
- Always mention user's role and department when available
- Break down by activity type (created/approved/reviewed)
- Include time context
- Show vendor diversity
- End with actionable insight
""",
            
            "vendor_query": """
VENDOR QUERY SPECIAL INSTRUCTIONS:
• Opening sentence with vendor name and summary
• Use bullets for key metrics and statistics
• Include vendor details (full name, shortform)
• Break down by status or category if applicable
• End with actionable insight

Example: "For Nimayate Creative Solutions (NCS), I found 8 invoices totaling ₹3,45,670.00:

Invoice Breakdown:
• Pending: 5 invoices - ₹2,10,450
• Cleared: 3 invoices - ₹1,35,220

Details:
• Date Range: 5 Nov - 18 Dec 2025
• Department: Primarily Marketing
• Average Invoice: ₹43,208.75

The majority of invoices are still pending clearance and should be prioritized."
""",
            
            "invoice_list": """
INVOICE LISTING SPECIAL INSTRUCTIONS:
• Brief intro with count and total
• List individual invoices as bullets with key details
• Keep each bullet to one line when possible
• Include: number, vendor, date, amount, status
• Group by status if helpful

Example: "Here are the 4 most recent invoices (Total: ₹1,15,250):
• INV-2024-020 - NCS (22 Jan) - ₹45,000.00 - Pending
• INV-2024-019 - ABC Corp (20 Jan) - ₹32,500.00 - Approved
• INV-2024-018 - XYZ Ltd (19 Jan) - ₹22,750.00 - Pending
• INV-2024-017 - NCS (18 Jan) - ₹15,000.00 - Cleared

Two invoices are pending approval and one has been cleared."
""",
            
            "purchase_order": """
PURCHASE ORDER SPECIAL INSTRUCTIONS:
• Include PO number, vendor name, date, and amounts
• Mention approval status and who approved it
• Show CGST, SGST, and grand total separately if available
• Link to related invoices if mentioned

Example: "Purchase Order PO-2024-015 was issued to ABC Corporation on 10 Jan 2024 for ₹50,000 plus ₹9,000 GST (total: ₹59,000). It was approved by the HOD and is currently active."
""",
            
            "filtered_list": """
FILTERED LIST SPECIAL INSTRUCTIONS:
• Explicitly mention what filter was applied
• Show count and provide representative examples
• Include totals, ranges, or distributions
• Highlight any interesting patterns

Example: "I found 12 invoices pending HOD approval, submitted between 5-15 Jan 2024. The amounts range from ₹5,000 to ₹85,000, with a total value of ₹3,45,600."
""",
            
            "general": """
GENERAL QUERY INSTRUCTIONS:
• Provide a clear, structured response
• Include all relevant information from the data
• Use natural language with proper context
• Format numbers and dates consistently
• End with a complete thought, not trailing off
"""
        }
        
        return instructions.get(query_type, instructions["general"])

    def _prepare_data_context(self, data: List[Dict], max_rows: int = 8) -> str:
        """Convert data to clean, readable JSON for LLM context"""
        if not data:
            return "No data available"
        
        # Convert data types that aren't JSON-serializable
        clean_data = []
        for row in data[:max_rows]:
            clean_row = {}
            for key, value in row.items():
                if isinstance(value, (Decimal, float)):
                    clean_row[key] = float(value)
                elif isinstance(value, (datetime, date)):
                    clean_row[key] = str(value)
                elif value is None:
                    clean_row[key] = None
                else:
                    clean_row[key] = str(value) if not isinstance(value, (int, bool)) else value
            clean_data.append(clean_row)
        
        return json.dumps(clean_data, indent=2, ensure_ascii=False, default=str)

    def _format_empty_response(self, message: str) -> str:
        """Format a helpful response when no data is found"""
        return f"""I couldn't find any records matching "{message}".

This could be because:
• No data exists for these specific criteria
• The vendor name, invoice number, or reference might be spelled differently
• The time period or date range specified has no matching entries
• The filter conditions are too restrictive

Would you like to try:
• Rephrasing your query with different terms?
• Searching for a broader date range?
• Checking the spelling of vendor names or invoice numbers?"""

    async def _regenerate_response(self, original_prompt: str, data: List[Dict], message: str) -> str:
        """Regenerate response if first attempt was too short"""
        
        enhanced_prompt = original_prompt + """

⚠️ CRITICAL: Your previous response was TOO SHORT and incomplete.

You MUST now provide a COMPLETE, DETAILED response that includes:
✓ Minimum 5-6 complete sentences
✓ Specific numbers, amounts, and dates from the actual data
✓ Proper context explaining what the data means
✓ Professional formatting with clear structure
✓ Natural, conversational language

DO NOT just state a single number or give a one-sentence answer.
EXPAND with full details and make it comprehensive.

Generate the complete response now:"""
        
        try:
            response = await self.qwen.call(enhanced_prompt, temperature=0.7, max_tokens=1500)
            response = response.strip()
        
            response = self._clean_response(response)
            if not response:
                return self._fallback_response(data, message)
            
            return response
        except Exception as e:
            logger.error(f"Regeneration failed: {e}")
            return self._fallback_response(data, message)

    def _fallback_response(self, data: List[Dict], message: str) -> str:
        """Simple fallback response if AI formatting completely fails"""
        if not data or len(data) == 0:
            return "I couldn't find any matching records for your query."
        
        count = len(data)
        
        # Try to extract and sum amount fields
        total = 0
        amount_field = None
        for key in ['total_amount', 'invoice_amount', 'grand_total', 'total', 'amount']:
            if key in data[0]:
                amount_field = key
                try:
                    total = sum(float(row.get(key, 0) or 0) for row in data)
                except (ValueError, TypeError):
                    total = 0
                break
        
        # Build a basic but complete response
        if amount_field and total > 0:
            return (f"I found {count} record{'s' if count != 1 else ''} matching your query "
                   f"with a total amount of ₹{total:,.2f}. The detailed information is "
                   f"displayed in the data table below for your review.")
        
        return (f"I found {count} record{'s' if count != 1 else ''} matching your query. "
               f"Please check the data table below for complete details and information.")

# ============================================================================
# GLOBAL INSTANCES
# ============================================================================

try:
    qwen_client = QwenClient()
    logger.info("✅ Qwen client ready")
except Exception as e:
    logger.error(f"❌ Qwen client init failed: {str(e)}")
    qwen_client = None

try:
    intent_analyzer = IntentAnalyzer()
    logger.info("✅ Intent analyzer ready")
except Exception as e:
    logger.error(f"❌ Intent analyzer init failed: {str(e)}")
    intent_analyzer = None

try:
    sql_generator = SQLGenerator()
    logger.info("✅ SQL generator ready (GPT-OSS)")
except Exception as e:
    logger.error(f"❌ SQL generator init failed: {str(e)}")
    sql_generator = None

try:
    response_formatter = ResponseFormatter()
    logger.info("✅ Response formatter ready")
except Exception as e:
    logger.error(f"❌ Response formatter init failed: {str(e)}")
    response_formatter = None