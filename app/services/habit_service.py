from datetime import datetime, timedelta, date
from app.database import get_database
from bson import ObjectId
import pytz


def generate_daily_occurrence(habit: dict, target_date: date):
    tz = pytz.timezone(habit["timezone"])

    due_start = tz.localize(
        datetime.combine(target_date, habit["time_window_start"])
    )
    due_end = tz.localize(
        datetime.combine(target_date, habit["time_window_end"])
    )

    return {
        "habit_id": str(habit["_id"]),
        "user_id": habit["user_id"],
        "scheduled_date": target_date,
        "due_start": due_start,
        "due_end": due_end,
        "status": "pending",
        "completed_at": None,
    }


def generate_occurrences(habit_id: str, days: int = 30):
    db = get_database()
    habit = db.habits.find_one({"_id": ObjectId(habit_id)})

    if not habit:
        return

    today = date.today()

    occurrences = []
    for i in range(days):
        target_date = today + timedelta(days=i)
        occurrence = generate_daily_occurrence(habit, target_date)
        occurrences.append(occurrence)

    if occurrences:
        db.habit_occurrences.insert_many(occurrences)


def auto_mark_missed():
    db = get_database()
    now = datetime.utcnow()

    db.habit_occurrences.update_many(
        {
            "status": "pending",
            "due_end": {"$lt": now},
        },
        {
            "$set": {"status": "missed"}
        }
    )
