import os
from pymongo import MongoClient
from app.config import settings

# Global database connection
client = None
db = None

def get_database():
    global client, db
    if db is None:
        client = MongoClient(settings.MONGODB_URI)
        db = client.get_database()
        print("MongoDB connected successfully")
    return db

# For FastAPI startup event
async def init_db():
    get_database()
