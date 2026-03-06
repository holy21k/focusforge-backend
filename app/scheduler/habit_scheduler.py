from datetime import datetime, timedelta
from app.database import get_database


def run_daily_habit_check():
    """
    Runs every day.
    Marks missed habits for the previous day.
    Updates streaks.
    """

    db = get_database()
    today_utc = datetime.utcnow().date()
    target_date = today_utc - timedelta(days=1)
    target_datetime = datetime.combine(target_date, datetime.min.time())

    habits = db.habits.find({"is_active": True})

    for habit in habits:
        habit_id = str(habit["_id"])
        user_id = habit["user_id"]

        # Check if already logged for the target day in habit_occurrences
        existing = db.habit_occurrences.find_one({
            "habit_id": habit_id,
            "user_id": user_id,
            "scheduled_date": target_datetime
        })

        if existing:
            continue

        # Mark as missed
        db.habit_occurrences.insert_one({
            "habit_id": habit_id,
            "user_id": user_id,
            "scheduled_date": target_datetime,
            "due_start": target_datetime,
            "status": "missed",
            "created_at": datetime.utcnow()
        })

        # Reset streak
        db.habits.update_one(
            {"_id": habit["_id"]},
            {"$set": {"current_streak": 0}}
        )
