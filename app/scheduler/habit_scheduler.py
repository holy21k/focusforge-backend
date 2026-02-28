from datetime import datetime, timedelta
from app.database import get_database


def run_daily_habit_check():
    """
    Runs every day.
    Marks missed habits.
    Updates streaks.
    """

    db = get_database()
    today_utc = datetime.utcnow().date()
    today_datetime = datetime.combine(today_utc, datetime.min.time())

    habits = db.habits.find({"is_active": True})

    for habit in habits:
        habit_id = str(habit["_id"])
        user_id = habit["user_id"]

        # Check if already logged today in habit_occurrences
        existing = db.habit_occurrences.find_one({
            "habit_id": habit_id,
            "user_id": user_id,
            "scheduled_date": today_datetime
        })

        if existing:
            continue

        # Mark as missed
        db.habit_occurrences.insert_one({
            "habit_id": habit_id,
            "user_id": user_id,
            "scheduled_date": today_datetime,
            "due_start": today_datetime,
            "status": "missed",
            "created_at": datetime.utcnow()
        })

        # Reset streak
        db.habits.update_one(
            {"_id": habit["_id"]},
            {"$set": {"current_streak": 0}}
        )
