# security_manager.py

import hashlib
import secrets

class SecurityManager:
    
    @staticmethod
    def hash_password(password):
        """Hashes a password with a random salt using PBKDF2."""
        salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000  # Recommended iterations
        )
        return key.hex(), salt

    @staticmethod
    def verify_password(stored_password_hash, salt, provided_password):
        """Verifies a provided password against a stored hash and salt."""
        key = hashlib.pbkdf2_hmac(
            'sha256',
            provided_password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        return key.hex() == stored_password_hash