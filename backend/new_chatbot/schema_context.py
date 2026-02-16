"""
Schema context builder for LLM prompts.
Generates rich schema descriptions to help AI understand the database structure.
"""
from typing import Dict, List
from .database import db


class SchemaContextBuilder:
    """Builds schema context for LLM prompts."""
    
    # Detailed descriptions for each table
    TABLE_DESCRIPTIONS = {
        "users": "Stores user accounts with authentication details (email, OTP), roles, and department assignments",
        "invoices": "Main invoice records with billing details, amounts, GST, approval workflow status, and payment clearance tracking",
        "purchase_orders": "Purchase order documents with vendor info, amounts, tax (CGST/SGST), and PDF attachments",
        "purchase_order_items": "Line items within purchase orders containing product descriptions, quantities, rates, and totals",
        "vendors": "Vendor/supplier master data with contact info, GSTIN, PAN, and status",
        "activity_log": "Audit trail of all user actions in the system"
    }
    
    # Detailed column descriptions
    COLUMN_DESCRIPTIONS = {
        "invoices": {
            "invoice_date": "Date when invoice was issued by vendor",
            "date_received": "Date when invoice was received by the company",
            "date_submission": "Date when invoice was submitted for processing",
            "invoice_amount": "Base invoice amount before GST",
            "gst": "GST (Goods and Services Tax) amount",
            "total_amount": "Final total = invoice_amount + gst",
            "invoice_cleared": "Whether payment has been released (Yes/No)",
            "invoice_cleared_date": "Date when payment was cleared",
            "po_number": "Reference to linked purchase order",
            "msme": "Whether vendor is MSME registered (Yes/No)",
            "isd": "Whether vendor is ISD registered (Yes/No)",
            "hod_values": "HOD (Head of Department) approval status/values",
            "ceo_values": "CEO approval status/values",
            "reviewed_by": "Email of user who reviewed this invoice",
            "approved_by": "Email of user who approved this invoice",
            "created_by": "Email of user who created this invoice",
            "tag1": "Custom tag for categorization (e.g., Urgent, Priority)",
            "tag2": "Secondary custom tag",
            "po_approved": "Whether the linked PO is approved (Yes/No)",
            "agreement_signed": "Whether vendor agreement is signed (Yes/No)",
            "deleted_at": "Soft delete timestamp (NULL if not deleted)",
            "deleted_by": "Email of user who deleted this invoice"
        },
        "purchase_orders": {
            "po_number": "Unique purchase order number",
            "vendor_id": "Foreign key to vendors table",
            "po_date": "Date when PO was created",
            "total_amount": "Base total before taxes",
            "cgst_amount": "Central GST amount",
            "sgst_amount": "State GST amount", 
            "grand_total": "Final total including all taxes",
            "pdf_path": "File path to uploaded PO PDF",
            "approved_by": "User ID who approved the PO",
            "reviewed_by": "User ID who reviewed the PO",
            "created_by": "User ID who created the PO",
            "vendor_address": "Vendor address for this PO",
            "deleted_at": "Soft delete timestamp"
        },
        "purchase_order_items": {
            "po_id": "Foreign key to purchase_orders table",
            "product_description": "Description of the product/service",
            "quantity": "Number of units ordered",
            "rate": "Price per unit",
            "line_total": "quantity × rate"
        },
        "vendors": {
            "vendor_name": "Full registered name of the vendor",
            "vendor_status": "Active or Inactive status",
            "department": "Department this vendor is associated with",
            "shortforms_of_vendors": "Abbreviated name or alias",
            "PAN": "Permanent Account Number (tax ID)",
            "GSTIN": "GST Identification Number",
            "POC": "Point of Contact name",
            "POC_number": "Contact phone number",
            "POC_email": "Contact email address"
        },
        "users": {
            "email": "User's email (used for login)",
            "name": "Full name of the user",
            "role": "User role (user, admin, hod, ceo)",
            "is_active": "Whether account is active (1) or disabled (0)",
            "department": "Department the user belongs to",
            "otp": "One-time password for authentication",
            "otp_created_at": "When OTP was generated",
            "otp_attempts": "Number of OTP verification attempts"
        },
        "activity_log": {
            "user_email": "Email of user who performed the action",
            "action": "Description of the action performed",
            "timestamp": "When the action occurred",
            "department": "Department context of the action"
        }
    }
    
    # Important business rules encoded
    BUSINESS_RULES = [
        "Invoices with invoice_cleared='Yes' are considered paid/cleared",
        "Invoices with invoice_cleared='No' are pending payment",
        "ONLY invoices and purchase_orders tables have deleted_at column for soft delete",
        "Vendors table does NOT have deleted_at - use vendor_status='Active' for active vendors",
        "Active vendors have vendor_status='Active'",
        "For pending approval: hod_values or ceo_values may be NULL or empty",
        "Invoice workflow: created -> reviewed -> approved -> cleared",
        "PO workflow: created -> reviewed -> approved",
        "MSME vendors have priority payment requirements",
        "Finance year (FY) runs from April to March (e.g., FY 2025-26 = April 2025 to March 2026)",
        
        # CRITICAL: User name matching rules
        "In invoices table: created_by, approved_by, reviewed_by, hod_values, ceo_values store FULL NAMES like 'Mrunal Salvi', 'Hemant Dhivar'",
        "In users table: name column stores full name, email column stores email address like 'mrunal.salvi@auxilo.com'",
        "When searching for user names, use LIKE with wildcards for partial matching: WHERE created_by LIKE '%Mrunal%'",
        "To match a user by first name only (e.g., 'mrunal'), use: created_by LIKE '%Mrunal%' OR use JOIN with users table",
        "'processed by' typically means created_by, approved_by, or reviewed_by - check all if unclear"
    ]

    def __init__(self):
        self._schema = None
    
    def get_full_schema_context(self) -> str:
        """Generate complete schema context for SQL generation."""
        if self._schema is None:
            self._schema = db.get_schema()
        
        context_parts = []
        context_parts.append("=== DATABASE SCHEMA ===\n")
        
        for table_name, table_info in self._schema.items():
            desc = self.TABLE_DESCRIPTIONS.get(table_name, "")
            context_parts.append(f"\n-- Table: {table_name}")
            context_parts.append(f"-- Description: {desc}")
            context_parts.append(f"-- Row count: {table_info['row_count']}")
            context_parts.append("-- Columns:")
            
            col_descs = self.COLUMN_DESCRIPTIONS.get(table_name, {})
            for col in table_info["columns"]:
                col_desc = col_descs.get(col["name"], "")
                key_info = f", {col['key']}" if col["key"] else ""
                nullable = "NULL" if col["nullable"] else "NOT NULL"
                
                line = f"--   {col['name']} ({col['type']}, {nullable}{key_info})"
                if col_desc:
                    line += f" - {col_desc}"
                if "enum_values" in col:
                    line += f" [Values: {', '.join(col['enum_values'])}]"
                if "sample_values" in col:
                    line += f" [Examples: {', '.join(col['sample_values'][:5])}]"
                
                context_parts.append(line)
        
        # Add relationships
        context_parts.append("\n\n=== TABLE RELATIONSHIPS ===")
        relationships = db.get_table_relationships()
        for table, rels in relationships.items():
            for col, ref in rels.items():
                context_parts.append(f"-- {table}.{col} -> {ref}")
        
        # Add business rules
        context_parts.append("\n\n=== BUSINESS RULES ===")
        for rule in self.BUSINESS_RULES:
            context_parts.append(f"-- {rule}")
        
        return "\n".join(context_parts)
    
    def get_relevant_schema_for_intent(self, intent: str, entities: Dict) -> str:
        """Get schema context relevant to a specific intent."""
        # For now, return full schema - can be optimized later
        return self.get_full_schema_context()
    
    def get_column_names_for_table(self, table_name: str) -> List[str]:
        """Get list of column names for a table."""
        if self._schema is None:
            self._schema = db.get_schema()
        
        if table_name in self._schema:
            return [col["name"] for col in self._schema[table_name]["columns"]]
        return []
    
    def get_all_table_names(self) -> List[str]:
        """Get list of all table names."""
        if self._schema is None:
            self._schema = db.get_schema()
        return list(self._schema.keys())


# Global instance
schema_context = SchemaContextBuilder()
