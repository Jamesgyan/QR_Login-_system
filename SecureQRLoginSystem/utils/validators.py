# utils/validators.py
import re
from datetime import datetime

def validate_email(email):
    """Basic email validation."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Validates phone as exactly 10 digits."""
    return phone.isdigit() and len(phone) == 10

def validate_date_format(date_str):
    """Validates date as YYYY-MM-DD."""
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False