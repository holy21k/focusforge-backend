"""
Task Scheduler - Auto-mark missed tasks at end of day
"""
from app.database import get_database
from datetime import datetime, date, timedelta
from bson import ObjectId


def auto_mark_missed_tasks():
    """
    Automatically mark all overdue uncompleted tasks as missed.
    This runs at the end of each day (after grace period).
    """
    db = get_database()
    today = date.today()
    
    # Grace period: tasks are marked missed 1 day after due date
    grace_period_end = today - timedelta(days=1)
    
    # Find all tasks that are:
    # 1. Not completed
    # 2. Not already marked as missed
    # 3. Due date is more than 1 day ago (past grace period)
    overdue_tasks = list(db.tasks.find({
        "is_completed": False,
        "is_missed": {"$ne": True},
        "due_date": {"$lt": datetime.combine(grace_period_end, datetime.min.time())}
    }))
    
    now = datetime.utcnow()
    missed_count = 0
    
    # Group by user and update
    user_tasks = {}
    for task in overdue_tasks:
        user_id = task["user_id"]
        if user_id not in user_tasks:
            user_tasks[user_id] = []
        user_tasks[user_id].append(task["_id"])
    
    for user_id, task_ids in user_tasks.items():
        result = db.tasks.update_many(
            {"_id": {"$in": task_ids}, "user_id": user_id},
            {"$set": {
                "is_missed": True,
                "missed_at": now,
                "updated_at": now
            }}
        )
        missed_count += result.modified_count
    
    return {
        "missed_count": missed_count,
        "timestamp": now.isoformat()
    }


def run_scheduler():
    """Run the task scheduler"""
    return auto_mark_missed_tasks()


if __name__ == "__main__":
    result = run_scheduler()
    print(f"Auto-marked {result['missed_count']} tasks as missed at {result['timestamp']}")
