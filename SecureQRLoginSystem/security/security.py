# security/security.py
import hashlib
import secrets

class SecurityManager:
    
    @staticmethod
    def get_salt():
        """Generates a secure random salt."""
        return secrets.token_hex(16)

    @staticmethod
    def hash_password(password, salt):
        """Hashes a password with PBKDF2."""
        pwd_bytes = password.encode('utf-8')
        salt_bytes = salt.encode('utf-8')
        hashed = hashlib.pbkdf2_hmac(
            'sha256',
            pwd_bytes,
            salt_bytes,
            100000  # 100,000 iterations
        )
        return hashed.hex()

    @staticmethod
    def verify_password(stored_password_hex, salt, provided_password):
        """Verifies a provided password against a stored hash."""
        return stored_password_hex == SecurityManager.hash_password(provided_password, salt)