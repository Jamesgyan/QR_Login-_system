# config/settings.py
import os
import platform
import sys

def get_app_data_dir():
    """
    Gets the appropriate cross-platform directory for app data.
    """
    system = platform.system()
    
    #
    # THIS IS THE FIX:
    # The 'if getattr(sys, 'frozen', False)...' block has been removed.
    # The code will now *always* use the correct AppData path below.
    #

    if system == 'Windows':
        # %APPDATA%/SecureQRLoginSystem
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
        app_dir = os.path.join(base, 'SecureQRLoginSystem')
    elif system == 'Darwin': # macOS
        # ~/Library/Application Support/SecureQRLoginSystem
        base = os.path.expanduser('~/Library/Application Support')
        app_dir = os.path.join(base, 'SecureQRLoginSystem')
    else: # Linux and other Unix-like
        # ~/.config/SecureQRLoginSystem
        base = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
        app_dir = os.path.join(base, 'SecureQRLoginSystem')
        
    # This check now runs for both regular Python and the compiled .exe
    if not os.path.exists(app_dir):
        os.makedirs(app_dir, exist_ok=True)
        
    return app_dir

# --- Constants ---
APP_DATA_DIR = get_app_data_dir()
DATABASE_PATH = os.path.join(APP_DATA_DIR, 'secure_qr_login.db')
QR_CODE_DIR = os.path.join(APP_DATA_DIR, 'qr_codes')

# Ensure QR code directory exists
os.makedirs(QR_CODE_DIR, exist_ok=True)

# Employee ID prefix
ID_PREFIX = "ALLY"
