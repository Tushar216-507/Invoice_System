# Invoice Management System — Technical Documentation

> **Version:** 2.0 (February 2026)  
> **Stack:** Python 3 · Flask · MySQL (AWS RDS) · Groq AI · ReportLab  
> **Last Updated:** 14 Feb 2026

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture](#2-architecture)
3. [Project Structure](#3-project-structure)
4. [Technology Stack & Dependencies](#4-technology-stack--dependencies)
5. [Configuration & Environment Variables](#5-configuration--environment-variables)
6. [Database Schema](#6-database-schema)
7. [Application Layer (`app_duplicate.py`)](#7-application-layer-app_duplicatepy)
8. [Backend Module (`backend/`)](#8-backend-module-backend)
9. [AI Chatbot Engine (`backend/new_chatbot/`)](#9-ai-chatbot-engine-backendnew_chatbot)
10. [Frontend (Templates & Static Assets)](#10-frontend-templates--static-assets)
11. [Authentication & Security](#11-authentication--security)
12. [Notification Services](#12-notification-services)
13. [PDF Generation](#13-pdf-generation)
14. [Automated Reports](#14-automated-reports)
15. [API Reference](#15-api-reference)
16. [Deployment](#16-deployment)
17. [Error Handling & Logging](#17-error-handling--logging)

---

## 1. System Overview

The **Invoice Management System** is a full-stack web application designed for [Auxilo](https://www.auxilo.com) to manage vendor invoices and purchase orders with a built-in AI-powered chatbot. Key capabilities include:

- **Invoice CRUD** — Create, read, update, and soft-delete invoices with approval workflows.
- **Purchase Order (PO) Management** — Create POs with auto-generated PO numbers and downloadable PDF output.
- **Vendor Management** — Vendor request/approval workflow with soft-delete support.
- **Admin Dashboard** — Financial year analytics, spending trends by tag & vendor, and chart-based visualizations.
- **AI Chatbot** — Natural-language querying of invoice/PO data via a multi-agent LLM pipeline.
- **WhatsApp Notifications** — Automated vendor notifications via the DICE API when invoices are cleared.
- **Monthly Reports** — Scheduled email-based Excel reports.
- **User Management** — OTP-based authentication, role-based access control (Super Admin / Admin / User).
- **Activity Logging** — Complete audit trail of all user actions.

---

## 2. Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                         CLIENT (Browser)                       │
│  HTML Templates  ·  chatbot.js  ·  dashboard.js  ·  po-mgmt.js│
└──────────────────────────┬─────────────────────────────────────┘
                           │ HTTP / AJAX
┌──────────────────────────▼─────────────────────────────────────┐
│                    Flask Application Server                     │
│                     (app_duplicate.py)                          │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────────┐ │
│  │ Auth &   │ │ Invoice  │ │ PO Mgmt   │ │ Admin Dashboard  │ │
│  │ Login    │ │ CRUD     │ │ & PDF Gen │ │ & Analytics      │ │
│  └──────────┘ └──────────┘ └───────────┘ └──────────────────┘ │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────────┐ │
│  │ Vendor   │ │ User     │ │ Activity  │ │ WhatsApp Notif.  │ │
│  │ Approval │ │ Mgmt     │ │ Logs      │ │ Service          │ │
│  └──────────┘ └──────────┘ └───────────┘ └──────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │            AI Chatbot Endpoint (/chat_v2)               │   │
│  └───────────────────────┬─────────────────────────────────┘   │
└──────────────────────────┼─────────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────────┐
│           AI Chatbot Engine (backend/new_chatbot/)             │
│                                                                 │
│  ┌──────────────┐  ┌───────────┐  ┌─────────────────────────┐ │
│  │ Unified      │→ │ Smart SQL │→ │ Response Formatter      │ │
│  │ Analyzer     │  │ Generator │  │ (Natural Language Out)   │ │
│  │ (Intent +    │  │ + Self-   │  └─────────────────────────┘ │
│  │  Entities +  │  │ Validation│                               │
│  │  Ambiguity)  │  └───────────┘                               │
│  └──────────────┘                                              │
│      ↓ Groq API (LLM)         ↓ Groq API (LLM)                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Conversation Manager · Schema Context · Prompts · Config │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────┬─────────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────────┐
│             MySQL Database (AWS RDS - ap-south-1)              │
│  Tables: invoices, vendors, users, purchase_orders,            │
│          purchase_order_items, dropdown_values, activity_log,  │
│          vendor_requests                                       │
└────────────────────────────────────────────────────────────────┘
```

---

## 3. Project Structure

```
invoice_chatbot_new_03-02-2026/
├── requirements.txt                  # Root-level dependencies (FastAPI, Groq, etc.)
├── venv/                             # Python virtual environment
└── invoice_updated/                  # Main application directory
    ├── .env                          # Environment variables (secrets, DB config)
    ├── Procfile                      # Gunicorn deployment config
    ├── requirements.txt              # Application dependencies
    ├── app.py                        # Original Flask app (1,331 lines)
    ├── app_duplicate.py              # Active Flask app (4,221 lines) ← MAIN ENTRY POINT
    ├── utils.py                      # Utility functions (amount_to_words, date formatting)
    │
    ├── backend/
    │   ├── __init__.py
    │   ├── db.py                     # DatabaseManager class (connection pooling, CRUD, fuzzy search)
    │   ├── db_enhanced.py            # Enhanced DB methods (fuzzy search, entity matching)
    │   ├── api_schemas.py            # ResponseBuilder & DateRangeHelper for API responses
    │   │
    │   ├── new_chatbot/              # AI Chatbot Module
    │   │   ├── __init__.py           # Module exports
    │   │   ├── config.py             # Configuration (DB, Groq API, AI models)
    │   │   ├── database.py           # Chatbot-specific DatabaseManager (connection pooling)
    │   │   ├── schema_context.py     # SchemaContextBuilder (table descriptions for LLM)
    │   │   ├── prompts.py            # All LLM prompt templates
    │   │   ├── conversation_manager.py # Session/conversation state management
    │   │   ├── chatbot.py            # Chatbot v1 (legacy)
    │   │   ├── chatbot_v2.py         # Chatbot v2 orchestrator (active)
    │   │   │
    │   │   └── agents/               # AI Agent Pipeline
    │   │       ├── unified_analyzer.py    # Intent + entities + ambiguity detection
    │   │       ├── smart_sql.py           # SQL generation + self-validation
    │   │       ├── sql_generator.py       # Standalone SQL generator (v1)
    │   │       ├── sql_validator.py       # SQL safety & correctness validation
    │   │       ├── ambiguity_detector.py  # Hybrid name collision detection
    │   │       ├── intent_classifier.py   # Intent classification & entity extraction
    │   │       └── response_formatter.py  # Natural language response formatting
    │   │
    │   └── old_backup/               # Legacy backend code
    │
    ├── templates/                    # Jinja2 HTML templates (14 files)
    │   ├── base.html                 # Base layout with sidebar, navbar, chatbot widget
    │   ├── login.html                # Login page
    │   ├── otp.html                  # OTP verification page
    │   ├── index.html                # Invoice list page (main dashboard)
    │   ├── add_invoice.html          # Invoice creation form
    │   ├── edit_invoice.html         # Invoice editing form
    │   ├── admin_dashboard.html      # Admin analytics dashboard
    │   ├── manage_vendors.html       # Vendor management page
    │   ├── manage_users.html         # User management page (superadmin)
    │   ├── manage_dropdowns.html     # Dropdown value management
    │   ├── approvals.html            # Vendor approval queue
    │   ├── activity_logs.html        # Activity log viewer
    │   ├── po_list.html              # Purchase orders list
    │   └── invoice_template.html     # Invoice PDF template
    │
    ├── static/
    │   ├── css/                      # Stylesheets
    │   ├── js/
    │   │   ├── chatbot.js            # Chatbot frontend logic (19.8 KB)
    │   │   ├── dashboard.js          # Dashboard charts & analytics
    │   │   ├── po-management.js      # PO creation/editing logic
    │   │   └── approvals.js          # Vendor approval UI logic
    │   ├── images/                   # Static images
    │   ├── excel_templates/          # Excel report templates
    │   ├── logo.png                  # Company logo
    │   └── sidebar-logo.png          # Sidebar logo
    │
    ├── generated_pdfs/               # Generated PO/Invoice PDFs
    ├── logs/                         # Application log files
    └── backup_code/                  # Code backups
```

---

## 4. Technology Stack & Dependencies

### Backend
| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Web Framework** | Flask | HTTP routing, request handling, Jinja2 templating |
| **Database** | MySQL 8.x (AWS RDS) | Persistent data storage |
| **ORM** | Flask-SQLAlchemy | User & activity log models |
| **DB Connector** | mysql-connector-python | Direct MySQL queries for most operations |
| **AI/LLM** | Groq API | LLM inference for chatbot (multiple models) |
| **PDF Generation** | ReportLab | Purchase Order PDF rendering |
| **Email** | Flask-Mail (SMTP) | OTP delivery & monthly report distribution |
| **Authentication** | Flask-Login | Session management with OTP-based auth |
| **Security** | Flask-WTF (CSRF) | CSRF protection |
| **Rate Limiting** | Flask-Limiter | API rate limiting (200/day, 50/hour) |
| **Excel** | openpyxl, pandas | Excel report generation & data export |

### AI Models (via Groq API)
| Agent | Model | Rationale |
|-------|-------|-----------|
| Ambiguity Detector | `llama-3.1-8b-instant` | Fast classification |
| Intent Classifier | `llama-3.3-70b-versatile` | Best for entity extraction |
| SQL Generator | `openai/gpt-oss-120b` | Excellent SQL reasoning |
| Response Formatter | `qwen/qwen3-32b` | Good text generation |
| Fallback | `llama-3.3-70b-versatile` | General-purpose fallback |

### Frontend
| Component | Technology |
|-----------|-----------|
| **Templates** | Jinja2 (server-side rendering) |
| **Styling** | CSS (with sidebar, responsive layout) |
| **JavaScript** | Vanilla JS + AJAX for chatbot & dashboard |
| **Charts** | Chart.js (embedded in admin dashboard) |

### Dependencies (`requirements.txt`)
```
Flask, Flask-SQLAlchemy, Flask-Mail, Flask-Login, Flask-WTF, Flask-Limiter, Flask-CORS
mysql-connector-python, python-dotenv, pandas, openpyxl
groq, openai, requests
xhtml2pdf, reportlab, num2words
python-dateutil, sqlparse, pydantic
gunicorn (production server)
```

---

## 5. Configuration & Environment Variables

All configuration is loaded from `.env` via `python-dotenv`.

| Variable | Description |
|----------|-------------|
| `APP_SECRET_KEY` | Flask session secret key |
| `DB_HOST` | MySQL host (AWS RDS endpoint) |
| `DB_USER` | Database username |
| `DB_PASSWORD` | Database password |
| `DB_NAME` | Database name (`invoice_uat_db`) |
| `SQLALCHEMY_DATABASE_URI` | Full SQLAlchemy connection URI |
| `MAIL_SERVER` | SMTP server (Office 365) |
| `MAIL_PORT` | SMTP port (587) |
| `MAIL_USERNAME` / `MAIL_PASSWORD` | Email credentials |
| `GROQ_API_KEY` | Groq API key for AI models |
| `QWEN_BASE_URL` / `QWEN_API_KEY` | Local Ollama endpoint (optional) |
| `REPORT_EMAIL_RECIPIENTS` | Comma-separated email list for monthly reports |

### Chatbot-Specific Config (`backend/new_chatbot/config.py`)

The `Config` class centralizes chatbot settings:
- **Database settings** — Host, user, password, name, port
- **AI model assignments** — Task-specific model routing to distribute Groq rate limits
- **Query settings** — `MAX_QUERY_RESULTS=100`, `QUERY_TIMEOUT=30s`, `MAX_RETRIES=3`
- **Validation** — `Config.validate()` ensures `GROQ_API_KEY` and DB config are present

---

## 6. Database Schema

The application uses a MySQL database (`invoice_uat_db`) hosted on AWS RDS. Core tables:

### `invoices`
Primary table for invoice records.
| Column | Type | Description |
|--------|------|-------------|
| `id` | INT (PK) | Auto-increment ID |
| `vendor` | VARCHAR | Vendor name |
| `invoice_number` | VARCHAR | Unique invoice identifier |
| `invoice_date` | DATE | Date of invoice |
| `amount` | DECIMAL | Invoice amount |
| `department` | VARCHAR | Department (e.g., Marketing) |
| `tag1` | VARCHAR | Category tag |
| `status` | ENUM | Status (Pending, Approved, Cleared, etc.) |
| `created_by` | VARCHAR | User email who created |
| `approved_by` | VARCHAR | User email who approved |
| `reviewed_by` | VARCHAR | User email who reviewed |
| `po_number` | VARCHAR | Associated PO number |
| `deleted_at` | DATETIME | Soft-delete timestamp (NULL = active) |

### `vendors`
| Column | Type | Description |
|--------|------|-------------|
| `id` | INT (PK) | Auto-increment ID |
| `vendor_name` | VARCHAR | Full vendor name |
| `shortforms_of_vendors` | VARCHAR | Abbreviations (e.g., "NCS" for Nimayate) |
| `vendor_status` | VARCHAR | Active/Inactive status |
| `department` | VARCHAR | Department |
| `vendor_address` | TEXT | Address |
| `PAN` / `GSTIN` | VARCHAR | Tax identifiers |
| `POC` / `POC_number` / `POC_email` | VARCHAR | Point of contact details |

### `users`
| Column | Type | Description |
|--------|------|-------------|
| `id` | INT (PK) | Auto-increment ID |
| `email` | VARCHAR (unique) | Login email |
| `name` | VARCHAR | Full name |
| `role` | VARCHAR | `superadmin`, `admin`, `user` |
| `department` | VARCHAR | Department |
| `is_active` | BOOLEAN | Active status |
| `otp` / `otp_expiry` | VARCHAR / DATETIME | OTP authentication fields |

### `purchase_orders`
| Column | Type | Description |
|--------|------|-------------|
| `id` | INT (PK) | Auto-increment ID |
| `po_number` | VARCHAR | PO number (format: `FY25-26/VENDOR-DATE/N`) |
| `vendor_id` | INT (FK) | References `vendors.id` |
| `created_by` / `approved_by` / `reviewed_by` | INT (FK) | References `users.id` |
| `deleted_at` | DATETIME | Soft-delete support |

### `purchase_order_items`
Line items within a PO.
| Column | Type | Description |
|--------|------|-------------|
| `id` | INT (PK) | Auto-increment ID |
| `po_id` | INT (FK) | References `purchase_orders.id` |
| (item details) | Various | Description, quantity, rate, amount, etc. |

### Other Tables
- **`dropdown_values`** — Configurable dropdown values for forms
- **`activity_log`** — Audit trail (user, action, timestamp, department)
- **`vendor_requests`** — Pending vendor approval requests

### Key Relationships
```
invoices.vendor        → vendors.vendor_name
invoices.created_by    → users.email
invoices.po_number     → purchase_orders.po_number
purchase_orders.vendor_id → vendors.id
purchase_order_items.po_id → purchase_orders.id
activity_log.user_email → users.email
```

---

## 7. Application Layer (`app_duplicate.py`)

The main Flask application file (4,221 lines) is the active entry point. It contains all route definitions, middleware, and service initializations.

### Key Classes

| Class | Lines | Purpose |
|-------|-------|---------|
| `Users` | 1235–1247 | SQLAlchemy user model with Flask-Login integration |
| `ActivityLog` | 1253–1258 | SQLAlchemy model for audit logging |
| `WhatsAppNotificationService` | 765–923 | DICE API integration for WhatsApp vendor notifications |

### Route Groups

#### Authentication (Lines 1304–1396)
| Route | Method | Description |
|-------|--------|-------------|
| `/login` | GET | Render login page |
| `/send_otp` | POST | Generate & email 6-digit OTP |
| `/verify_otp` | POST | Verify OTP and create session |
| `/otp` | GET | OTP input page |
| `/logout` | GET | Destroy session |

#### Invoice Management (Lines 1399–2825)
| Route | Method | Description |
|-------|--------|-------------|
| `/` (index) | GET | List invoices with filters (vendor, status, date, department, tag) |
| `/add_invoice` | GET/POST | Multi-step invoice creation with email notifications |
| `/edit_invoice/<id>` | GET/POST | Edit invoice with approval workflow |
| `/delete_invoice/<id>` | POST | Soft-delete invoice |
| `/download_excel` | GET | Export filtered invoices to Excel |
| `/download_single_excel/<id>` | GET | Export single invoice to Excel |

#### Admin Dashboard (Lines 1550–1938)
| Route | Method | Description |
|-------|--------|-------------|
| `/admin_dashboard` | GET | Analytics dashboard with FY-based charts |
| `/api/tag1_trends` | GET | AJAX endpoint for Tag1 spending trends |
| `/api/vendor_trends` | GET | AJAX endpoint for vendor spending trends |
| `/api/month_spend` | GET | AJAX endpoint for monthly spend data |
| `/api/top_criteria` | GET | AJAX endpoint for top spending criteria |
| `/api/invoices` | GET | Paginated invoice data API |

#### Vendor Management (Lines 2827–3180)
| Route | Method | Description |
|-------|--------|-------------|
| `/manage_vendors` | GET | List all vendors |
| `/edit_vendor/<id>` | GET/POST | Edit vendor details |
| `/request_vendor` | POST | Submit vendor for approval |
| `/approvals` | GET | View pending vendor approvals (superadmin) |
| `/approve_vendor/<id>` | POST | Approve vendor request |
| `/reject_vendor/<id>` | POST | Reject vendor request |
| `/soft_delete_vendor/<id>` | POST | Soft-delete vendor |

#### User Management (Lines 3251–3363) — *Superadmin Only*
| Route | Method | Description |
|-------|--------|-------------|
| `/manage_users` | GET | List all users |
| `/add_user` | POST | Create new user |
| `/delete_user/<id>` | POST | Delete user |
| `/toggle_user_status/<id>` | POST | Toggle active/inactive |
| `/update_user_role/<id>` | POST | Change user role |

#### Purchase Order System (Lines 3668–4163)
| Route | Method | Description |
|-------|--------|-------------|
| `/po_list` | GET | List all POs |
| `/add_po` | GET/POST | Create PO with line items |
| `/download_po_pdf/<id>` | GET | Generate & download PO PDF |
| `/po_detail/<id>` | GET | View PO details |
| `/update_po/<id>` | POST | Update PO |
| `/delete_po/<id>` | POST | Soft-delete PO |
| `/po_activities` | GET | PO activity logs |
| `/generate_po_number` | POST | Generate next PO number for vendor |

#### Chatbot Endpoints (Lines 709–984)
| Route | Method | Description |
|-------|--------|-------------|
| `/chat` | POST | Legacy chatbot endpoint (v1) |
| `/chat_v2` | POST | Enhanced chatbot with hybrid disambiguation (v2) |

#### Activity & Reporting
| Route | Method | Description |
|-------|--------|-------------|
| `/activity_logs` | GET | View activity logs |
| `/download_activity_logs` | GET | Export activity logs to CSV |
| `/total_logs_count` | GET | Get total log count |

---

## 8. Backend Module (`backend/`)

### `db.py` — DatabaseManager

Central database layer used by the main app for direct MySQL queries.

**Key Methods:**
| Method | Description |
|--------|-------------|
| `connect()` | Establish MySQL connection |
| `disconnect()` | Close connection |
| `reconnect()` | Reconnect if connection lost |
| `execute_query(sql, params)` | Execute SELECT query, return results |
| `execute_update(sql, params)` | Execute INSERT/UPDATE/DELETE |
| `get_schema()` | Return full database schema as formatted string |
| `get_tables()` | List all tables |
| `get_table_info(table)` | Detailed table information |
| `fuzzy_search_entities(term, threshold)` | Fuzzy search across users & vendors |
| `get_entity_invoice_count(type, name)` | Count invoices for a vendor/user |
| `get_vendor_by_id(id)` / `get_user_by_id(id)` | Entity retrieval |
| `execute_query_with_logging(sql, params)` | Query with performance logging & slow-query warnings |
| `test_connection()` | Health check |

### `api_schemas.py` — Response Builders

**`ResponseBuilder`** — Static methods for consistent API responses:
- `needs_entity_clarification(...)` — When multiple vendor/user matches found
- `needs_date_range(...)` — When date range selection is required
- `query_success(...)` — Successful query response with data
- `error_response(...)` — Standardized error response
- `no_matches_found(...)` — No results found
- `ambiguous_query(...)` — Query needs clarification

**`DateRangeHelper`** — Date utility:
- `get_date_range(quick_pick)` — Convert "this_month", "last_quarter", etc. to actual dates
- `validate_date_range(from, to)` — Validate date range inputs

---

## 9. AI Chatbot Engine (`backend/new_chatbot/`)

### Pipeline Overview

The chatbot uses a **3-step pipeline** (v2) orchestrated by `InvoiceChatbotV2`:

```
User Question
     │
     ▼
┌─────────────────────────┐
│  Step 1: Unified        │  (Single LLM call)
│  Analyzer               │
│  • Intent classif.      │
│  • Entity extraction    │
│  • Ambiguity detection  │
│  • Name collision check │
│  (Hybrid: rules + LLM)  │
└───────────┬─────────────┘
            │
     Needs clarification? ──Yes──▶ Ask user, wait for response
            │ No
            ▼
┌─────────────────────────┐
│  Step 2: Smart SQL      │  (Single LLM call)
│  Generator              │
│  • Generate MySQL query │
│  • Self-validate SQL    │
│  • Auto-retry on error  │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Step 3: Response       │  (LLM or rule-based)
│  Formatter              │
│  • Execute SQL query    │
│  • Format as markdown   │
│  • Indian ₹ formatting  │
│  • Card-style display   │
└───────────┬─────────────┘
            │
            ▼
       Response to User
```

### Module Breakdown

#### `chatbot_v2.py` — Orchestrator
**`InvoiceChatbotV2`** (main class):
- `chat(question, session_id)` — Process user question through the 3-step pipeline
- `_handle_clarification_response(session_id, user_response)` — Handle follow-up to clarification
- `_process_with_analysis(session_id, question, analysis)` — Process with pre-computed analysis

**`ChatResponse`** (dataclass):
- `message`, `needs_clarification`, `clarifying_question`, `options`, `sql_query`, `data`, `session_id`, `success`, `error`

#### `conversation_manager.py` — Session State
Manages multi-turn conversations with in-memory session storage.

**Data Classes:**
- `Message` — Single message with role, content, timestamp, metadata
- `ClarificationState` — Tracks pending clarification (original question, options, type)
- `ConversationSession` — Full session (history, pending clarification, resolved clarifications, context)

**`ConversationManager` Methods:**
- `create_session()` / `get_session(id)` / `get_or_create_session(id)`
- `add_message(session_id, role, content)`
- `get_history_text(session_id, max_messages=10)`
- `set_pending_clarification(...)` / `has_pending_clarification(...)` / `resolve_clarification(...)`
- `get_context_for_prompt(session_id)`

#### `schema_context.py` — Database Schema for LLM
**`SchemaContextBuilder`** provides rich schema descriptions to LLM prompts:
- `TABLE_DESCRIPTIONS` — Human-readable descriptions for all tables
- `COLUMN_DESCRIPTIONS` — Per-table column-level descriptions
- `IMPORTANT_RULES` — Critical business rules (soft-delete columns, active vendors, etc.)
- `get_full_schema_context()` — Generate complete schema context string
- `get_relevant_schema_for_intent(intent, entities)` — Optimized schema for specific intents
- `get_column_names_for_table(table)` / `get_all_table_names()`

#### `prompts.py` — LLM Prompt Templates
Centralized prompt templates for all AI agents:

| Prompt | Purpose |
|--------|---------|
| `AMBIGUITY_DETECTOR_PROMPT` | Detect ambiguous queries, check vendor/user name collisions |
| `INTENT_CLASSIFIER_PROMPT` | Classify intent (invoice_query, vendor_query, analytics, etc.) |
| `SQL_GENERATOR_PROMPT` | Generate MySQL queries with context-aware rules |
| `SMART_SQL_PROMPT` | Combined SQL generation + validation |
| `RESPONSE_FORMATTER_PROMPT` | Format query results as natural language |
| `UNIFIED_ANALYZER_PROMPT` | Single-call analysis (intent + entities + ambiguity) |

**Key Prompt Rules:**
- Only generate SELECT statements (no DROP, DELETE, UPDATE, INSERT, ALTER)
- Use LIKE with wildcards for partial name matching
- Indian currency formatting (₹ with lakh/crore format)
- PO number detection patterns (e.g., `FY25-26/XXX-DATE/N`)
- Follow-up query handling via conversation context
- LIMIT rules based on user intent

### Agent Modules (`agents/`)

#### `unified_analyzer.py` — UnifiedAnalyzer
Combines ambiguity detection + intent classification + entity extraction in a single LLM call. Uses a **hybrid approach**: rule-based name collision check first, then LLM for complex cases.

**Key Methods:**
- `analyze(question, history, skip_collision_check)` — Full analysis
- `_check_name_collision(question)` — Rule-based: checks if name exists in BOTH vendors AND users
- `_is_context_clear(question)` — Checks for clear vendor/user context keywords
- `_get_vendor_data()` / `_get_user_data()` — Cache vendor/user first names from DB
- `parse_clarification_response(options, user_response)` — Parse user's clarification selection

**Output Format:**
```json
{
  "can_proceed": true/false,
  "intent": "invoice_query",
  "entities": {"vendor": "Google", "status": "pending"},
  "tables": ["invoices"],
  "clarification": { "question": "...", "options": [...] },
  "reasoning": "..."
}
```

#### `smart_sql.py` — SmartSQL
Generates SQL queries with self-validation in a single LLM call.

**Key Methods:**
- `generate(question, intent, entities, tables, history, clarifications, retry_count, previous_error)`
- `generate_with_retry(...)` — Auto-retry with self-correction (feeds error back to model)

**Safety Features:**
- Only allows SELECT statements
- Blocks dangerous SQL keywords
- Auto-retry up to 2 times with error context

#### `sql_validator.py` — SQLValidator
Rule-based SQL validation (no LLM required).

**Validation Checks:**
1. Must start with SELECT
2. No dangerous keywords (DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, etc.)
3. SQL injection pattern detection (comment injection, OR injection, UNION injection)
4. SQL syntax parsing via `sqlparse`
5. Table name validation against schema
6. Query complexity warnings (>5 JOINs)

**Output:** `{ is_valid, issues[], safety_score (0.0–1.0), corrected_sql }`

#### `ambiguity_detector.py` — AmbiguityDetector
Hybrid ambiguity detection for vendor/user name collisions.

**Approach:**
1. Load known vendor & user names from database
2. Extract potential names from question using NLP patterns
3. Check for name collisions (name exists in both vendors & users)
4. Use phrase patterns to determine if context is clear
5. Fall back to LLM for complex cases

**Methods:**
- `detect_ambiguity(question, history)` — Full ambiguity analysis
- `check_name_collision(question)` — Quick collision check
- `parse_clarification_response(...)` — Parse user selection

#### `intent_classifier.py` — IntentClassifier
Classifies user intents into categories.

**Intent Types:**
| Intent | Description |
|--------|-------------|
| `invoice_query` | Questions about invoices |
| `purchase_order_query` | Questions about POs |
| `vendor_query` | Questions about vendors |
| `user_query` | Questions about users |
| `activity_log_query` | Questions about activity logs |
| `analytics` | Spending trends, summaries |
| `comparison` | Comparing entities |
| `export` | Data export requests |

#### `response_formatter.py` — ResponseFormatter
Converts query results into user-friendly natural language.

**Formatting Strategies:**
- **Empty results** → Friendly "no data found" message
- **Single aggregate** → Direct value with context
- **Multiple rows** → Card-style formatting with headers
- **Complex results** → LLM-based formatting with markdown

**Formatting Rules:**
- Currency in Indian format: `₹1,00,000.00`
- Dates in `DD MMM YYYY` format
- Bold headers, bullet points, and clear structure
- Strips LLM thinking/reasoning tags from output

#### `database.py` — Chatbot DatabaseManager
Dedicated database connection pool for the chatbot module (separate from the main app's connection).

**Features:**
- MySQL connection pooling (pool size: 5)
- Schema introspection with caching
- Table relationship inference
- Health check endpoint
- Context manager support (`with db.get_connection() as conn`)

---

## 10. Frontend (Templates & Static Assets)

### Template Hierarchy
All templates extend `base.html` which provides:
- **Sidebar navigation** — Links to all major sections
- **Top navbar** — User info, notifications, logout
- **Chatbot widget** — Floating chat button with expandable chat window
- **Flash message handling** — Success/error notifications

### Key Templates

| Template | Purpose | Notable Features |
|----------|---------|-----------------|
| `base.html` | Master layout | Sidebar, navbar, chatbot widget, CSRF meta tag |
| `index.html` | Invoice list | DataTables, filters (status, vendor, dept, date), pagination |
| `add_invoice.html` | Create invoice | Multi-field form, vendor dropdown, file upload, tag selection |
| `edit_invoice.html` | Edit invoice | Pre-populated form, approval workflow buttons |
| `admin_dashboard.html` | Analytics | Chart.js charts (spending trends, vendor analysis, tag breakdown) |
| `manage_vendors.html` | Vendor CRUD | Vendor table, edit/delete actions, approval status |
| `manage_users.html` | User mgmt | Role assignment, status toggle, user creation |
| `po_list.html` | PO list | PO cards, status filters, PDF download |

### JavaScript Modules

| File | Size | Purpose |
|------|------|---------|
| `chatbot.js` | 19.8 KB | Full chatbot UI: message bubbles, AJAX to `/chat_v2`, clarification option buttons, session management, auto-scroll, typing indicators |
| `dashboard.js` | 5.9 KB | Chart.js initialization, AJAX data fetching for trends, responsive chart updates |
| `po-management.js` | 15 KB | PO form logic: dynamic line items, vendor selection, PO number generation, calculation of totals, PDF preview |
| `approvals.js` | 3.5 KB | Vendor approval/rejection UI, modal dialogs, AJAX submissions |

---

## 11. Authentication & Security

### Authentication Flow
```
Login Page → Enter Email → Send OTP (via email) → Enter OTP → Verify → Session Created
```

1. **OTP Generation** — Cryptographically secure 6-digit OTP via `secrets` module
2. **OTP Hashing** — SHA-256 hashed before storing in database
3. **OTP Expiry** — 5-minute expiry window
4. **Session Management** — Flask-Login with `LoginManager`
5. **Session Cookie Config** — HTTPOnly, SameSite=Strict

### Security Measures
| Measure | Implementation |
|---------|---------------|
| **CSRF Protection** | Flask-WTF `CSRFProtect` on all POST forms |
| **Rate Limiting** | Flask-Limiter: 200 requests/day, 50 requests/hour |
| **Role-Based Access** | Decorators: `@login_required`, `@superadmin_required` |
| **SQL Safety** | Parameterized queries, SQL keyword blacklist, injection pattern detection |
| **Cache Prevention** | Response headers: `no-store, no-cache, must-revalidate` |
| **Safe Queries Only** | Chatbot blocks all non-SELECT statements |
| **Input Validation** | Server-side validation on all form submissions |

### Role Hierarchy
| Role | Permissions |
|------|-------------|
| `superadmin` | All actions: user management, vendor approval, settings |
| `admin` | Invoice CRUD, vendor management, dashboard access |
| `user` | Invoice creation, basic viewing, chatbot access |

---

## 12. Notification Services

### Email Notifications (Flask-Mail)
- **OTP Delivery** — Send 6-digit OTP to user's registered email
- **Monthly Reports** — Scheduled Excel report to configured recipients
- **SMTP Config** — Office 365 (smtp.office365.com:587, TLS)

### WhatsApp Notifications (`WhatsAppNotificationService`)
Sends automated WhatsApp messages to vendors when invoices are cleared.

**Integration:** DICE API (OAuth2 token-based)

**Flow:**
1. Cache OAuth token with expiry tracking
2. `send_invoice_cleared_notification(vendor_name, invoice_number, cleared_date, mobile_no)`
3. Sends templated WhatsApp message via DICE API endpoint

---

## 13. PDF Generation

### Purchase Order PDFs (ReportLab)
Generated by `generate_po_pdf_flask(data)` in `app_duplicate.py`.

**Features:**
- A4 page size with company logo header
- Structured table layout with line items
- Amount in words (Indian English format via `num2words`)
- Custom page layout with header/footer
- Auto-generated filename: `PO_{po_number}.pdf`
- Stored in `generated_pdfs/` directory

---

## 14. Automated Reports

### Monthly Invoice Report
**Function:** `run_monthly_report()` → `get_monthly_summary()` → `create_monthly_excel()` → `send_monthly_email()`

**Process:**
1. Calculate previous month's date range
2. Fetch summary statistics (total invoices, amounts by status)
3. Fetch detailed invoice data
4. Generate Excel workbook with `openpyxl`:
   - Summary sheet (totals, averages, breakdowns)
   - Detailed sheet (all invoices for the period)
5. Email Excel attachment to configured recipients

---

## 15. API Reference

### Chatbot API

#### `POST /chat_v2`
Enhanced chatbot endpoint (v2).

**Request:**
```json
{
  "message": "Show pending invoices from Google",
  "session_id": "optional-uuid"
}
```

**Response:**
```json
{
  "message": "**Found 5 pending invoices from Google:**\n• INV-001 - ₹1,50,000...",
  "session_id": "uuid-v4",
  "needs_clarification": false,
  "sql_query": "SELECT * FROM invoices WHERE vendor LIKE '%Google%' AND status='Pending'",
  "data": [...],
  "success": true
}
```

**Clarification Response:**
```json
{
  "needs_clarification": true,
  "clarifying_question": "I found 'Hemant' as both a vendor and a user...",
  "options": ["Vendor: Hemant Enterprises", "User: Hemant Dhivar"]
}
```

### Dashboard APIs

| Endpoint | Method | Returns |
|----------|--------|---------|
| `GET /api/tag1_trends?fy=2025-2026&tag=Marketing` | GET | Monthly trend data for Chart.js |
| `GET /api/vendor_trends?fy=2025-2026&vendor=Google` | GET | Vendor spending trends |
| `GET /api/month_spend?fy=2025-2026&month=1` | GET | Monthly spend breakdown |
| `GET /api/top_criteria?fy=2025-2026` | GET | Top spending criteria |
| `GET /api/invoices?page=1&per_page=25` | GET | Paginated invoice data |

### Vendor Approval APIs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `POST /request_vendor` | POST | Submit vendor request |
| `GET /api/pending_count` | GET | Count of pending approvals |
| `GET /api/vendor_request/<id>` | GET | Vendor request details |
| `POST /approve_vendor/<id>` | POST | Approve vendor (superadmin) |
| `POST /reject_vendor/<id>` | POST | Reject vendor (superadmin) |

---

## 16. Deployment

### Production Configuration

**Procfile:**
```
web: gunicorn app:app --timeout 120 --workers 5
```

### Environment
- **Platform:** Gunicorn WSGI server
- **Workers:** 5 workers with 120s timeout
- **Database:** AWS RDS MySQL (ap-south-1 region)
- **Port:** 5000 (development), standard 80/443 (production)

### Running Locally
```bash
# Activate virtual environment for linux
python -m venv venv
source venv/bin/activate

# Activate virtual environment for Windows
python -m venv venv
venv/Scripts/activate

# Install dependencies
pip install -r invoice_updated/requirements.txt

# Run development server
cd invoice_updated
python3 app_duplicate.py    # Starts on http://0.0.0.0:5000
```

---

## 17. Error Handling & Logging

### Logging Configuration
- **Development:** `INFO` level
- **Production:** `WARNING` level
- **File Handler:** `RotatingFileHandler` in `logs/` directory
- **Format:** Includes timestamp, level, module, and message

### Global Error Handlers
| HTTP Code | Handler | Response |
|-----------|---------|----------|
| 400 | `bad_request(e)` | JSON error response |
| 403 | `forbidden(e)` | JSON error response |
| 404 | `not_found(e)` | JSON error response |
| 500 | `internal_error(e)` | JSON error response |
| All others | `handle_exception(e)` | Generic error with logging |

### Chatbot Error Handling
- **LLM failures** → Fallback model (`llama-3.3-70b-versatile`)
- **SQL parsing errors** → Return user-friendly error message
- **Query execution errors** → Auto-retry with self-correction (up to 3 attempts)
- **JSON parse failures** → Default analysis with basic intent guessing
- **Database connection issues** → Reconnect logic with pool management

---

> **Note:** `app.py` (1,331 lines) is the original/simpler version of the application. The production-active file is `app_duplicate.py` (4,221 lines), which contains all features including the enhanced chatbot, WhatsApp notifications, PO system, and admin dashboard.
