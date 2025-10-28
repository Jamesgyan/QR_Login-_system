# config_manager.py

import os
import sys
from pathlib import Path

APP_NAME = "SecureQRLoginSystem"

def get_app_data_dir():
    """
    Gets the appropriate application data directory based on the OS.
    """
    if sys.platform == "win32":
        base_dir = os.environ.get("APPDATA")
    elif sys.platform == "darwin":
        base_dir = Path.home() / "Library/Application Support"
    else: # Linux and other Unix-like
        base_dir = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    
    app_dir = Path(base_dir) / APP_NAME
    return app_dir

# Define application paths
APP_DIR = get_app_data_dir()
DB_PATH = APP_DIR / "secure_qr_login.db"
QR_DIR = APP_DIR / "qr_codes"

def setup_directories():
    """
    Creates the necessary application directories if they don't exist.
    """
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        QR_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Data directory set up at: {APP_DIR}")
    except Exception as e:
        print(f"Error setting up directories: {e}")
        # In a real app, you might want to exit or show a GUI error