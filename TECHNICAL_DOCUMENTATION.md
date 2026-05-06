# Invoice Management System - Technical Documentation

> Version: 2.1 (March 2026)
> Stack: Python 3, Flask, MySQL, Groq AI, ReportLab
> Last Updated: 31 Mar 2026

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture](#2-architecture)
3. [Project Structure](#3-project-structure)
4. [Technology Stack and Dependencies](#4-technology-stack-and-dependencies)
5. [Configuration and Environment Variables](#5-configuration-and-environment-variables)
6. [Database Schema](#6-database-schema)
7. [Application Layer (`app.py`)](#7-application-layer-apppy)
8. [Backend Module (`backend/`)](#8-backend-module-backend)
9. [AI Chatbot Engine (`backend/new_chatbot/`)](#9-ai-chatbot-engine-backendnew_chatbot)
10. [Frontend](#10-frontend)
11. [Authentication and Security](#11-authentication-and-security)
12. [Notification Services](#12-notification-services)
13. [PDF Generation](#13-pdf-generation)
14. [Automated Reports](#14-automated-reports)
15. [API Reference](#15-api-reference)
16. [Deployment](#16-deployment)
17. [Error Handling and Logging](#17-error-handling-and-logging)

---

## 1. System Overview

The Invoice Management System is a Flask-based internal application for invoice, vendor, and purchase-order operations. It combines standard CRUD workflows with an AI chatbot that translates natural-language questions into safe SQL queries against the invoice database.

Key capabilities:

- Invoice create, edit, delete, export, and analytics workflows
- Purchase order creation, update, PDF generation, and download
- Vendor onboarding, approval, import, export, and soft-delete flows
- User management and role-based access control
- OTP-based login
- Admin dashboard with financial-year trend APIs
- AI chatbot with clarification handling and SQL safety checks
- Email notifications and DICE-based WhatsApp notifications
- Monthly Excel report generation and email delivery
- Centralized activity logging

---

## 2. Architecture

```text
Browser
  |
  | HTTP / AJAX
  v
Flask app (`invoice_updated/app.py`)
  |
  |-- Jinja templates and static assets
  |-- Auth, invoice, vendor, PO, dashboard, reporting routes
  |-- Email and WhatsApp notification services
  |-- SQLAlchemy models for users and activity logs
  |-- Direct MySQL queries via mysql-connector connection pooling
  |
  +--> Chatbot endpoints
         |
         v
      `backend/new_chatbot/`
         |
         |-- Unified analyzer
         |-- Smart SQL generator
         |-- SQL validator
         |-- Response formatter
         |
         v
      MySQL database (`invoices_v2`)
```

The same codebase supports local MySQL during development and hosted MySQL environments through `.env` configuration.

---

## 3. Project Structure

```text
invoice_chatbot_new_03-02-2026/
|-- requirements.txt
|-- app_duplicate.py
|-- venv/
`-- invoice_updated/
    |-- .env
    |-- Procfile
    |-- requirements.txt
    |-- SETUP_WINDOWS.md
    |-- TECHNICAL_DOCUMENTATION.md
    |-- app.py
    |-- utils.py
    |-- backend/
    |   `-- new_chatbot/
    |       |-- __init__.py
    |       |-- chatbot_v2.py
    |       |-- config.py
    |       |-- conversation_manager.py
    |       |-- database.py
    |       |-- prompts.py
    |       |-- schema_context.py
    |       `-- agents/
    |           |-- __init__.py
    |           |-- response_formatter.py
    |           |-- smart_sql.py
    |           |-- sql_validator.py
    |           `-- unified_analyzer.py
    |-- templates/
    |-- static/
    |-- generated_pdfs/
    |-- logs/
    `-- backup_code/
```

Notes:

- `invoice_updated/app.py` is the active Flask entry point.
- The root `requirements.txt` and `invoice_updated/requirements.txt` currently mirror the same pinned dependencies.
- `app_duplicate.py` exists in the repo, but the live app described in this document is `invoice_updated/app.py`.

---

## 4. Technology Stack and Dependencies

### Backend

| Component | Technology | Purpose |
|----------|----------|----------|
| Web framework | Flask | Routing, request handling, templates |
| ORM | Flask-SQLAlchemy | User and activity-log models |
| Database connector | mysql-connector-python | Main MySQL query execution |
| AI SDK | groq | Chatbot LLM calls |
| Additional AI SDK | openai | Imported in app-level code for AI integrations |
| Excel | pandas, openpyxl | Report generation and exports |
| PDF | ReportLab, xhtml2pdf | Purchase order and HTML-to-PDF support |
| Mail | Flask-Mail | OTP and report emails |
| Auth | Flask-Login | Session-based auth |
| CSRF | Flask-WTF | Form protection |
| Rate limiting | Flask-Limiter | Endpoint throttling |
| HTTP client | requests | DICE integrations |
| Imaging | Pillow | Logo/image handling |
| SQL parsing | sqlparse | Query validation in chatbot |

### AI Models

Configured in `invoice_updated/backend/new_chatbot/config.py`:

| Responsibility | Model |
|----------|----------|
| Ambiguity detector | `llama-3.1-8b-instant` |
| Intent classifier | `llama-3.3-70b-versatile` |
| SQL generator | `openai/gpt-oss-120b` |
| Response formatter | `qwen/qwen3-32b` |
| Fallback | `llama-3.3-70b-versatile` |

### Current pinned requirements

```txt
Flask==3.1.2
Flask-SQLAlchemy==3.1.1
Flask-Mail==0.10.0
Flask-Login==0.6.3
Flask-WTF==1.2.2
Flask-Limiter==4.1.1
mysql-connector-python==9.5.0
python-dotenv==1.2.1
pandas==3.0.0
openpyxl==3.1.5
num2words==0.5.14
openai==2.16.0
groq==1.0.0
sqlparse==0.5.5
requests==2.32.5
reportlab==4.4.9
Pillow==12.1.0
xhtml2pdf==0.2.17
gunicorn==23.0.0
```

---

## 5. Configuration and Environment Variables

Configuration is loaded from `.env` using `python-dotenv`.

### Core app settings

| Variable | Purpose |
|----------|----------|
| `APP_SECRET_KEY` | Flask secret key |
| `FLASK_ENV` | Development or production behavior |
| `DB_HOST` | MySQL host |
| `DB_USER` | MySQL username |
| `DB_PASSWORD` | MySQL password |
| `DB_NAME` | Database name |
| `DB_PORT` | Database port for chatbot config |
| `SQLALCHEMY_DATABASE_URI` | SQLAlchemy connection string |
| `SQLALCHEMY_TRACK_MODIFICATIONS` | SQLAlchemy event toggle |

### Mail settings

| Variable | Purpose |
|----------|----------|
| `MAIL_SERVER` | SMTP host |
| `MAIL_PORT` | SMTP port |
| `MAIL_USERNAME` | Sender username |
| `MAIL_PASSWORD` | Sender password |
| `MAIL_USE_TLS` | TLS toggle |
| `MAIL_USE_SSL` | SSL toggle |

### Chatbot settings

| Variable | Purpose |
|----------|----------|
| `GROQ_API_KEY` | Groq API key |
| `API_HOST` | Chatbot host default |
| `API_PORT` | Chatbot port default |

### DICE and notification settings

| Variable | Purpose |
|----------|----------|
| `DICE_API_USERNAME` | DICE username |
| `DICE_API_PASSWORD` | DICE password |
| `DICE_AUTH_URL` | DICE OAuth endpoint |
| `DICE_WHATSAPP_URL` | DICE WhatsApp API endpoint |
| `DICE_WHATSAPP_TEMPLATE_ID` | WhatsApp template ID |
| `WHATSAPP_ENABLED` | Enables WhatsApp notifications |
| `EMAIL_DICE_ENABLED` | Enables DICE-backed email service |
| `REPORT_EMAIL_RECIPIENTS` | Monthly report recipients |
| `INVOICE_ADDED_RECIPIENTS` | New invoice notification recipients |
| `VENDOR_ADDED_RECIPIENTS` | Vendor approval notification recipients |
| `WHATSAPP_INTERNAL_NUMBERS` | Internal WhatsApp notification numbers |

---

## 6. Database Schema

The application uses MySQL with the primary database name `invoices_v2`.

Core tables referenced in the app and chatbot:

- `invoices`
- `vendors`
- `users`
- `purchase_orders`
- `purchase_order_items`
- `dropdown_values`
- `activity_log`
- `vendor_requests`
- `activity_of_po`

Important relationships:

- `purchase_order_items.po_id -> purchase_orders.id`
- `purchase_orders.vendor_id -> vendors.id`
- `activity_log.user_email -> users.email`
- Invoice and analytics queries join vendor, user, and PO metadata as needed

Business rules encoded in application logic:

- Vendors can be soft-deleted
- User roles drive access to admin-only features
- Chatbot queries are restricted to read-only SQL
- Financial-year analytics run from April to March

---

## 7. Application Layer (`app.py`)

`invoice_updated/app.py` contains the active Flask app, route definitions, service initialization, SQLAlchemy models, reporting functions, and global error handling.

### Important classes and functions

| Item | Purpose |
|----------|----------|
| `Users` | SQLAlchemy user model with Flask-Login integration |
| `ActivityLog` | Audit log model |
| `WhatsAppNotificationService` | DICE-based WhatsApp integration |
| `EmailNotificationService` | DICE-based email helper |
| `generate_po_pdf_flask(data)` | Purchase-order PDF renderer |
| `run_monthly_report()` | Report generation entry point |

### Main route groups

#### Authentication

| Route | Method | Description |
|----------|----------|----------|
| `/` | GET | Login page |
| `/otp` | GET | OTP page |
| `/send-otp` | POST | Generate and send OTP |
| `/verify-otp` | POST | Verify OTP and create session |
| `/logout` | GET | End session |

#### Dashboard and analytics

| Route | Method | Description |
|----------|----------|----------|
| `/index` | GET, POST | Main invoice listing page |
| `/dashboard` | GET, POST | Admin dashboard |
| `/dashboard/` | GET, POST | Dashboard alias |
| `/api/tag1_trends` | GET | Tag-based financial-year trends |
| `/api/vendor_trends` | GET | Vendor trend data |
| `/api/month_spend` | GET | Monthly spend data |
| `/api/top_criteria` | GET | Top criteria summary |
| `/api/invoices` | GET, POST | Invoice API for dashboard tables |

#### Invoice operations

| Route | Method | Description |
|----------|----------|----------|
| `/add` | GET, POST | Add invoice |
| `/edit/<id>` | GET, POST | Edit invoice |
| `/delete/<id>` | POST | Delete invoice |
| `/download_excel` | POST | Export invoice data |
| `/download_single_excel/<id>` | GET | Export one invoice |

#### Vendor operations

| Route | Method | Description |
|----------|----------|----------|
| `/manage_vendors` | GET | Vendor management page |
| `/edit_vendor/<id>` | POST | Update vendor |
| `/vendor/add_department` | POST | Add vendor department |
| `/vendor/import/template` | GET | Download vendor import template |
| `/vendor/import/preview` | POST | Preview vendor import |
| `/vendor/import/confirm` | POST | Confirm vendor import |
| `/vendor/request` | POST | Submit vendor approval request |
| `/approvals` | GET | Pending vendor approvals |
| `/api/pending-count` | GET | Approval counter |
| `/vendor/request-details/<request_id>` | GET | Vendor request details |
| `/vendor/approve/<request_id>` | POST | Approve vendor request |
| `/vendor/reject/<request_id>` | POST | Reject vendor request |
| `/vendor/delete/<id>` | POST | Soft-delete vendor |
| `/vendor/export` | GET | Export vendors to Excel |

#### User and admin operations

| Route | Method | Description |
|----------|----------|----------|
| `/manage_users` | GET | User management |
| `/add_user` | POST | Add user |
| `/delete_user/<user_id>` | POST | Delete user |
| `/toggle_user_status/<user_id>` | POST | Activate/deactivate user |
| `/update_user_role/<user_id>` | POST | Change user role |
| `/manage_dropdowns` | GET, POST | Dropdown management |
| `/delete_dropdown/<id>` | POST | Delete dropdown value |
| `/activity_logs` | GET | Activity log page |
| `/download_activity_logs` | GET | Download logs |
| `/api/total_logs_count` | GET | Activity-log count |

#### Purchase orders

| Route | Method | Description |
|----------|----------|----------|
| `/po/list` | GET | PO list |
| `/po/add` | POST | Create PO |
| `/po/generate_number` | POST | Generate PO number |
| `/po/download/<po_id>` | GET | Download PO PDF |
| `/po/detail/<po_id>` | GET | PO details |
| `/po/update/<po_id>` | POST | Update PO |
| `/po/activities` | GET | PO activity log view |
| `/po/delete/<po_id>` | POST | Delete PO |

#### Chatbot

| Route | Method | Description |
|----------|----------|----------|
| `/api/chat` | POST | Legacy-compatible chatbot endpoint |
| `/api/chat/v2` | POST | Primary chatbot endpoint |

---

## 8. Backend Module (`backend/`)

The current `backend/` directory is focused on the chatbot package. There is no separate generic service layer under `backend/` in the live tree; most business logic still lives directly in `app.py`.

Current modules:

- `new_chatbot/__init__.py`: exports `chatbot_v2`
- `new_chatbot/chatbot_v2.py`: chatbot orchestration
- `new_chatbot/config.py`: model, database, and API configuration
- `new_chatbot/conversation_manager.py`: in-memory multi-turn state
- `new_chatbot/database.py`: chatbot-specific database manager and pooling
- `new_chatbot/prompts.py`: centralized prompt templates
- `new_chatbot/schema_context.py`: schema descriptions for prompt grounding
- `new_chatbot/agents/*`: pipeline components

---

## 9. AI Chatbot Engine (`backend/new_chatbot/`)

### Pipeline overview

The active chatbot is `InvoiceChatbotV2`, which runs a 3-step pipeline:

1. Unified analysis
2. SQL generation and validation
3. Result formatting

### High-level flow

```text
User question
  -> Unified analyzer
  -> Clarification if needed
  -> Smart SQL generation
  -> Rule-based SQL validation
  -> Query execution
  -> Response formatting
  -> JSON response to frontend
```

### Core modules

#### `chatbot_v2.py`

Main orchestrator:

- Creates or resumes conversation sessions
- Detects whether the user is answering a clarification
- Calls the unified analyzer
- Calls SQL generation and validation
- Executes the query through the chatbot DB layer
- Returns a `ChatResponse` dataclass

`ChatResponse` fields:

- `message`
- `needs_clarification`
- `clarifying_question`
- `options`
- `sql_query`
- `data`
- `session_id`
- `success`
- `error`

#### `conversation_manager.py`

Manages in-memory session state:

- message history
- pending clarification state
- resolved clarification values
- session IDs for follow-up questions

#### `database.py`

Provides chatbot-specific database access:

- MySQL connection pooling
- query execution
- schema access and caching
- context-manager helpers

#### `schema_context.py`

Supplies schema descriptions and business rules to the prompts:

- table descriptions
- column descriptions
- important query rules
- intent-specific schema narrowing

#### `prompts.py`

Stores the prompt templates used by the chatbot package, including:

- `AMBIGUITY_DETECTOR_PROMPT`
- `INTENT_CLASSIFIER_PROMPT`
- `SQL_GENERATOR_PROMPT`
- `SMART_SQL_PROMPT`
- `RESPONSE_FORMATTER_PROMPT`
- `UNIFIED_ANALYZER_PROMPT`

### Agent modules

#### `unified_analyzer.py`

Responsibilities:

- intent detection
- entity extraction
- ambiguity detection
- name-collision handling
- clarification-response parsing

This module replaces the need for separate active ambiguity and intent modules in the current live tree.

#### `smart_sql.py`

Responsibilities:

- generate SQL from the normalized question and context
- retry generation after execution failures
- keep output constrained to safe, read-only query patterns

#### `sql_validator.py`

Responsibilities:

- require `SELECT` queries
- block dangerous SQL keywords
- detect basic injection patterns
- parse SQL using `sqlparse`
- validate referenced tables and general safety

#### `response_formatter.py`

Responsibilities:

- convert SQL results into user-friendly text
- handle empty states
- format currency and summary responses
- keep frontend output readable

---

## 10. Frontend

The UI is server-rendered with Jinja templates and enhanced with JavaScript for chatbot, dashboard, and PO workflows.

### Important templates

| Template | Purpose |
|----------|----------|
| `base.html` | Shared shell, navigation, chatbot widget |
| `login.html` | Login page |
| `otp.html` | OTP verification |
| `index.html` | Invoice listing |
| `add_invoice.html` | Invoice creation |
| `edit_invoice.html` | Invoice editing |
| `admin_dashboard.html` | Dashboard charts and summaries |
| `manage_vendors.html` | Vendor management |
| `manage_users.html` | User management |
| `manage_dropdowns.html` | Dropdown management |
| `approvals.html` | Vendor approvals |
| `activity_logs.html` | Activity-log view |
| `po_list.html` | PO management view |
| `invoice_template.html` | Invoice/PDF template |

### Important JavaScript files

| File | Purpose |
|----------|----------|
| `static/js/chatbot.js` | Chatbot widget, AJAX calls, conversation handling |
| `static/js/dashboard.js` | Charts and dashboard refresh logic |
| `static/js/po-management.js` | PO line-item calculations and UI |
| `static/js/approvals.js` | Vendor approval UI actions |

---

## 11. Authentication and Security

### Authentication flow

1. User opens `/`
2. Frontend submits email to `/send-otp`
3. System generates a 6-digit OTP
4. OTP is hashed and stored against the user
5. OTP is delivered by email
6. User submits code to `/verify-otp`
7. On success, Flask-Login session is created

### Security measures

| Measure | Implementation |
|----------|----------|
| OTP generation | `secrets` module |
| OTP hashing | SHA-256 hashing before storage |
| OTP expiration | 5-minute validity window |
| OTP brute-force protection | Attempt counter and lockout |
| Session auth | Flask-Login |
| CSRF protection | Flask-WTF `CSRFProtect` |
| Rate limiting | Flask-Limiter |
| Query safety | parameterized SQL plus chatbot SQL validation |
| Session cookies | HTTPOnly and `SameSite=Strict` |
| Activity auditing | `ActivityLog` model and PO activity logging |

### Roles

- `superadmin`
- `admin`
- `user`

Role checks determine access to user management, approvals, and other privileged workflows.

---

## 12. Notification Services

### Email

Email functionality is used for:

- OTP delivery
- monthly Excel report delivery
- invoice and vendor related notifications

The app uses `Flask-Mail`, and an additional `EmailNotificationService` is present for DICE-backed email workflows.

### WhatsApp

`WhatsAppNotificationService` integrates with DICE:

- authenticates with OAuth-style token retrieval
- caches access tokens
- sends invoice-cleared notifications
- can notify internal recipients when configured

---

## 13. PDF Generation

Purchase-order PDFs are generated by `generate_po_pdf_flask(data)` in `invoice_updated/app.py`.

Features:

- A4 layout
- logo rendering
- line-item tables
- tax and grand-total display
- amount-in-words output through `num2words`
- generated file storage in `generated_pdfs/`

Filename behavior:

- uses the PO number when available
- falls back to timestamp-based names when PO number is absent

`xhtml2pdf` is imported defensively and may be unavailable without breaking the entire app.

---

## 14. Automated Reports

Monthly reporting is implemented in `app.py` through:

- `get_monthly_summary()`
- `create_monthly_excel(...)`
- `send_monthly_email(...)`
- `run_monthly_report()`

Report flow:

1. compute the target reporting period
2. gather summary and detailed invoice data
3. build an Excel workbook with `openpyxl`
4. email the report to configured recipients

---

## 15. API Reference

### Chatbot endpoints

#### `POST /api/chat`

Legacy-compatible endpoint. Internally calls the v2 chatbot and returns a simplified response shape.

Request:

```json
{
  "message": "Show pending invoices from Google",
  "conversation_id": "optional-session-id"
}
```

Response:

```json
{
  "success": true,
  "response": "Found matching invoices...",
  "conversation_id": "session-id",
  "error": false
}
```

#### `POST /api/chat/v2`

Primary chatbot endpoint with clarification support.

Request:

```json
{
  "message": "Show pending invoices from Google",
  "conversation_id": "optional-session-id"
}
```

Normal response:

```json
{
  "success": true,
  "response": "Found matching invoices...",
  "conversation_id": "session-id",
  "error": false,
  "sql_query": "SELECT ..."
}
```

Clarification response:

```json
{
  "success": true,
  "needs_clarification": true,
  "clarification_type": "entity_selection",
  "message": "Which one did you mean?",
  "options": ["Vendor: ...", "User: ..."],
  "conversation_id": "session-id",
  "response": "Which one did you mean?\n\n1. ...\n2. ..."
}
```

### Dashboard and analytics APIs

| Endpoint | Method | Description |
|----------|----------|----------|
| `/api/tag1_trends` | GET | Tag-level trend data |
| `/api/vendor_trends` | GET | Vendor trend data |
| `/api/month_spend` | GET | Monthly spend summary |
| `/api/top_criteria` | GET | Top-criteria summary |
| `/api/invoices` | GET, POST | Invoice data for dashboard tables |
| `/api/total_logs_count` | GET | Activity-log count |

### Vendor approval APIs

| Endpoint | Method | Description |
|----------|----------|----------|
| `/vendor/request` | POST | Submit vendor request |
| `/api/pending-count` | GET | Fetch pending request count |
| `/vendor/request-details/<request_id>` | GET | Fetch one request |
| `/vendor/approve/<request_id>` | POST | Approve request |
| `/vendor/reject/<request_id>` | POST | Reject request |

### Purchase order APIs

| Endpoint | Method | Description |
|----------|----------|----------|
| `/po/generate_number` | POST | Generate next PO number |
| `/po/add` | POST | Create PO |
| `/po/detail/<po_id>` | GET | Get PO details |
| `/po/update/<po_id>` | POST | Update PO |
| `/po/delete/<po_id>` | POST | Delete PO |
| `/po/download/<po_id>` | GET | Download PDF |

---

## 16. Deployment

### Procfile

```txt
web: gunicorn app:app --timeout 120 --workers 5
```

### Production notes

- `gunicorn` runs from the `invoice_updated` directory
- the exported WSGI object is `app`
- database connectivity is driven entirely by environment variables
- the same code can run against local MySQL or a managed MySQL service

### Local development

From the repository root:

```bash
python -m venv venv
```

Windows activation:

```bash
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the app:

```bash
cd invoice_updated
python app.py
```

The development server starts on `http://0.0.0.0:5000`.

---

## 17. Error Handling and Logging

### Logging

The app configures:

- environment-based log levels
- console logging
- rotating file logs under `invoice_updated/logs/`

Log behavior:

- `INFO` in non-production environments
- `WARNING` in production

### Flask error handlers

Configured handlers include:

- `400`
- `403`
- `404`
- `500`
- generic `Exception`

Behavior is mixed by route type:

- `400` returns JSON for bad requests
- `403`, `404`, and `500` generally flash a message and redirect
- generic exceptions are logged with stack traces
- in debug mode, the generic exception handler re-raises

### Chatbot error handling

- clarification fallback when user input is ambiguous
- SQL validation before execution
- retry generation after SQL execution errors
- user-friendly failure messages when LLM or DB steps fail

---

`invoice_updated/app.py` is the active application entry point documented here. If `app_duplicate.py` or backup copies are retained for reference, treat them as archival unless deployment configuration is explicitly changed.
