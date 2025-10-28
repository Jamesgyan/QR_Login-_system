from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId

class DatabaseManager:
    def __init__(self, connection_string="mongodb://localhost:27017/"):
        self.connection_string = connection_string
        self.client = None
        self.db = None
        self.users_collection = None
        self.attendance_collection = None
        self.connected = False
        
    def connect(self):
        try:
            self.client = MongoClient(self.connection_string, serverSelectionTimeoutMS=5000)
            self.client.server_info()
            self.db = self.client["gesture_login_db"]
            self.users_collection = self.db["users"]
            self.attendance_collection = self.db["attendance"]
            self.connected = True
            return True
        except Exception as e:
            self.connected = False
            self.error = str(e)
            return False
    
    def get_all_users(self):
        return list(self.users_collection.find({"face_registered": True}))
    
    def get_user(self, emp_id):
        return self.users_collection.find_one({"emp_id": emp_id})
    
    def create_user(self, emp_id, name):
        return self.users_collection.update_one(
            {"emp_id": emp_id},
            {"$set": {
                "name": name,
                "face_registered": True,
                "registered_on": datetime.now()
            }},
            upsert=True
        )
    
    def delete_user(self, emp_id):
        result = self.users_collection.delete_one({"emp_id": emp_id})
        return result.deleted_count > 0
    
    def log_attendance(self, emp_id, name, action, method="face"):
        log_data = {
            "emp_id": emp_id,
            "name": name,
            "action": action,
            "timestamp": datetime.now()
        }
        
        if method == "gesture":
            log_data["gesture"] = True
        elif method == "manual":
            log_data["manual"] = True
        elif method == "auto":
            log_data["auto"] = True
            
        return self.attendance_collection.insert_one(log_data)
    
    def get_attendance_records(self, emp_id=None, limit=100):
        query = {"emp_id": emp_id} if emp_id else {}
        return list(self.attendance_collection.find(query).sort("timestamp", -1).limit(limit))
    
    def get_logged_in_users(self):
        recent_logins = self.attendance_collection.aggregate([
            {"$match": {"action": "LOGIN"}},
            {"$sort": {"timestamp": -1}},
            {"$group": {"_id": "$emp_id", "latest_login": {"$first": "$timestamp"}}}
        ])
        
        logged_in_users = set()
        for login in recent_logins:
            latest_logout = self.attendance_collection.find_one(
                {"emp_id": login["_id"], "action": "LOGOUT", "timestamp": {"$gt": login["latest_login"]}},
                sort=[("timestamp", -1)]
            )
            if not latest_logout:
                logged_in_users.add(login["_id"])
                
        return logged_in_users
    
    def generate_employee_id(self):
        last_user = self.users_collection.find_one({}, sort=[("_id", -1)])
        if last_user and "emp_id" in last_user:
            last_id = last_user["emp_id"]
            if last_id.startswith("EMP"):
                try:
                    num = int(last_id[3:]) + 1
                    return f"EMP{num:04d}"
                except:
                    pass
        return "EMP0001"
    
    def close(self):
        if self.client:
            self.client.close()