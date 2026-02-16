from datetime import date, datetime
from num2words import num2words

def amount_to_words(amount: float) -> str:
    """Convert amount to words in Indian currency format"""
    try:
        # Convert to integer (paise not needed for PO)
        amount_int = int(amount)
        words = num2words(amount_int, lang='en_IN')
        # Capitalize first letter
        words = words.capitalize()
        return f"Rupees {words} Only"
    except:
        return f"Rupees {amount:.2f} Only"

def today_date():
    """Return today's date in DD/MM/YYYY format"""
    return date.today().strftime("%d/%m/%Y")

def format_date_for_db(date_str: str):
    """Convert DD/MM/YYYY to YYYY-MM-DD for database"""
    return datetime.strptime(date_str, "%d/%m/%Y").date()