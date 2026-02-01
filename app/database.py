# app/database.py

from pymongo import MongoClient
from app.config import settings

client = None
db = None

def get_database():
    """
    Returns the MongoDB database object.
    Initializes the client if not already connected.
    """
    global client, db

    if db is None:
        # Create the client
        client = MongoClient(settings.MONGODB_URI)
        
        # Extract the database name from URI or use default
        if client.get_default_database() is not None:
            db = client.get_default_database()
        else:
            # Fallback if URI has no database, use 'focusforge'
            db = client['focusforge']

        print(f"MongoDB connected successfully: {db.name}")

    return db

async def init_db():
    """
    Async placeholder for any DB initialization tasks.
    Currently, just ensures connection.
    """
    get_database()
