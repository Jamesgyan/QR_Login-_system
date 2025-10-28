# database/mongodb_service.py
from pymongo import MongoClient
import pickle

class MongoDBService:
    def __init__(self, connection_string="mongodb://localhost:27017/"):
        self.client = MongoClient(connection_string)
        self.db = self.client['auth_app']
        self.users = self.db['users']
    
    def create_user(self, user_data):
        result = self.users.insert_one(user_data)
        return result.inserted_id
    
    def find_user_by_id(self, user_id):
        return self.users.find_one({"_id": user_id})
    
    # Implement other methods similar to SQLite service