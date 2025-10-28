# main.py
from gui.main_app import MainApplication
from database.database import DatabaseManager
from security.security import SecurityManager
from core.qr_handler import QRHandler
from core.user_manager import UserManager
from core.auth_manager import AuthManager

def main():
    # 1. Initialize core components
    db_manager = DatabaseManager()
    security_manager = SecurityManager()
    qr_handler = QRHandler()
    
    # 2. Initialize managers (business logic)
    user_manager = UserManager(db_manager, security_manager, qr_handler)
    auth_manager = AuthManager(db_manager, security_manager)
    
    # 3. Initialize and run the application
    app = MainApplication(
        db_manager=db_manager,
        user_manager=user_manager,
        auth_manager=auth_manager,
        qr_handler=qr_handler
    )
    
    app.mainloop()

if __name__ == "__main__":
    main()