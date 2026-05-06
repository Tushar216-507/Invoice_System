"""
Configuration management for the Invoice Chatbot.
Loads environment variables and defines constants.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Find and load the .env file from invoice_updated directory
# This works whether we're in backend/new_chatbot or running from invoice_updated
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()  # Fallback to current directory



class Config:
    """Application configuration."""
    
    # Database settings
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "invoices_v2")
    DB_PORT = int(os.getenv("DB_PORT", 3306))
    
    # SQLAlchemy URI
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "SQLALCHEMY_DATABASE_URI",
        f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    
    # Groq API settings
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    
    # AI Models - Distributing across different models to avoid rate limits
    # Each model has its own rate limit quota on Groq's free tier
    #
    # Available models on Groq (Feb 2026):
    # - openai/gpt-oss-120b (fast, excellent reasoning)
    # - llama-3.3-70b-versatile (best general purpose)
    # - llama-3.1-8b-instant (fastest, lightweight)
    # - qwen/qwen3-32b (good reasoning)
    # - mistral-saba-24b (balanced)
    # - meta-llama/llama-4-scout-17b-16e-instruct (preview)
    
    # Task-specific model assignments (distributing load across quotas)
    MODEL_AMBIGUITY_DETECTOR = "llama-3.1-8b-instant"        # Fast classification
    MODEL_INTENT_CLASSIFIER = "llama-3.3-70b-versatile"      # Good for entity extraction
    MODEL_SQL_GENERATOR = "openai/gpt-oss-120b"              # Excellent SQL reasoning
    MODEL_RESPONSE_FORMATTER = "qwen/qwen3-32b"              # Good text generation
    
    # Fallback model (if primary fails)
    MODEL_FALLBACK = "llama-3.3-70b-versatile"
    
    # API settings
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", 8000))
    
    # Query settings
    MAX_QUERY_RESULTS = 100
    QUERY_TIMEOUT = 30  # seconds
    MAX_RETRIES = 3
    
    @classmethod
    def validate(cls) -> bool:
        """Validate that required configuration is present."""
        if not cls.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is required in .env file")
        if not cls.DB_HOST:
            raise ValueError("Database configuration is required")
        return True


config = Config()
