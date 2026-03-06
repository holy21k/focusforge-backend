from pymongo import MongoClient, ASCENDING
from app.config import settings
import logging

logger = logging.getLogger(__name__)
client = None
db = None

def get_database():
    global client, db
    if db is None:
        client = MongoClient(settings.MONGODB_URI)
        try:
            db = client.get_default_database()
        except Exception:
            db = client[settings.DB_NAME]
        logger.info(f"MongoDB connected: {db.name}")
    return db

async def init_db():
    database = get_database()

    def safe_index(collection, keys, **kwargs):
        try:
            collection.create_index(keys, **kwargs)
        except Exception as e:
            logger.warning(f"Index skipped: {e}")

    safe_index(database.habits, [("user_id", ASCENDING)])
    safe_index(database.tasks, [("user_id", ASCENDING)])
    safe_index(database.habit_occurrences, [("user_id", ASCENDING)])
    safe_index(database.habit_occurrences, [("habit_id", ASCENDING)])
    safe_index(database.user_ai_context, [("user_id", ASCENDING)], unique=True)
    safe_index(database.users, [("email", ASCENDING)], unique=True)
    safe_index(database.users, [("username", ASCENDING)], unique=True)

    logger.info("✅ MongoDB indexes created")