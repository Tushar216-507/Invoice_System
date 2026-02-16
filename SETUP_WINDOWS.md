# Invoice Chatbot - Windows Setup Guide

## Prerequisites

Before starting, install these on your Windows laptop:

### 1. Python 3.10+ 
Download from: https://www.python.org/downloads/
-  Check "Add Python to PATH" during installation

### 2. MySQL Server
Download from: https://dev.mysql.com/downloads/installer/
- Install MySQL Server and MySQL Workbench
- Remember the root password you set!

### 3. Git (optional, for cloning)
Download from: https://git-scm.com/download/win

---

## Step-by-Step Setup

### Step 1: Copy the Project

**Option A: Copy folder directly**
```
Copy the entire "invoice_updated" folder to your Windows machine
(via USB, OneDrive, email, etc.)
```

**Option B: Clone from Git (if using Git)**
```bash
git clone <your-repo-url>
cd invoice_updated
```

---

### Step 2: Open Command Prompt

1. Press `Win + R`
2. Type `cmd` and press Enter
3. Navigate to the project folder:

```cmd
cd C:\path\to\invoice_updated
```

---

### Step 3: Create Virtual Environment

```cmd
python -m venv venv
```

---

### Step 4: Activate Virtual Environment

```cmd
venv\Scripts\activate
```

You should see `(venv)` at the start of your command line.

---

### Step 5: Install Dependencies

```cmd
pip install flask flask-sqlalchemy flask-mail flask-login flask-wtf flask-limiter flask-cors
pip install mysql-connector-python pandas openpyxl num2words reportlab
pip install groq openai python-dotenv
```

---

### Step 6: Setup MySQL Database

1. Open **MySQL Workbench**
2. Connect to your local MySQL server
3. Create the database:

```sql
CREATE DATABASE invoice_uat_db;
```

4. Import your data:
   - Right-click on `invoice_uat_db`  **Table Data Import Wizard**
   - Or import from SQL dump file if you have one

---

### Step 7: Create .env File

Create a file named `.env` in the `invoice_updated` folder with this content:

```env
# Database Configuration
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password_here
DB_NAME=invoice_uat_db
DB_PORT=3306

# Groq API Key (get from https://console.groq.com)
GROQ_API_KEY=gsk_your_api_key_here

# Flask Configuration
SECRET_KEY=your-secret-key-here
FLASK_ENV=development
```

**Important:** Replace:
- `your_mysql_password_here` with your actual MySQL password
- `gsk_your_api_key_here` with your Groq API key

---

### Step 8: Run the Application

Make sure virtual environment is activated, then:

```cmd
python app_duplicate.py
```

You should see:
```
 * Running on http://127.0.0.1:5000
 * Debugger is active!
```

---

### Step 9: Access the Application

Open your browser and go to:
```
http://localhost:5000
```

---

## Quick Command Summary

```cmd
# Navigate to project
cd C:\path\to\invoice_updated

# Activate virtual environment
venv\Scripts\activate

# Run the app
python app_duplicate.py
```

---

## Troubleshooting

### Issue: "python is not recognized"
- Make sure Python is added to PATH during installation
- Or use: `py` instead of `python`

### Issue: "No module named ..."
- Make sure venv is activated: `venv\Scripts\activate`
- Install missing package: `pip install <package-name>`

### Issue: "Access denied for user 'root'@'localhost'"
- Check your MySQL password in `.env` file
- Make sure MySQL service is running

### Issue: "Rate limit exceeded" from Groq
- Wait for the rate limit to reset (usually 1 hour)
- Or get a new API key from https://console.groq.com

### Issue: "Connection refused" database error
- Make sure MySQL service is running
- Check: Services  MySQL  Start

---

## Getting a Groq API Key

1. Go to https://console.groq.com
2. Sign up / Log in
3. Go to **API Keys** section
4. Click **Create API Key**
5. Copy the key and paste in your `.env` file

---

## Project Structure

```
invoice_updated/
 app_duplicate.py       # Main Flask application
 .env                   # Environment variables (create this)
 backend/
    new_chatbot/       # Chatbot module
        chatbot.py     # Main chatbot orchestrator
        config.py      # Configuration
        database.py    # Database connection
        prompts.py     # AI prompts
        agents/        # AI agents
 static/                # CSS, JS, images
 templates/             # HTML templates
```

---

## Need Help?

If you encounter any issues:
1. Check the error message carefully
2. Make sure all prerequisites are installed
3. Verify `.env` file has correct values
4. Make sure MySQL is running
