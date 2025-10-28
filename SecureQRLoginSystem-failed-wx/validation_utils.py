# validation_utils.py

import re
from datetime import datetime

def validate_email(email):
    """Basic email validation."""
    if not email:
        return False
    # A standard, simplified email regex
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Validates phone number (exactly 10 digits)."""
    if not phone:
        return True # Phone can be optional
    return phone.isdigit() and len(phone) == 10

def validate_date_format(date_str):
    """Validates date string is in YYYY-MM-DD format."""
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False