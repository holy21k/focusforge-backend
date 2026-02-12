# FocusForge API Documentation

## Base URL
http://localhost:8000/api/v1

## Authentication
All protected endpoints require JWT token in header:
Authorization: Bearer {your_jwt_token}

---

## AUTHENTICATION

### 1. Register User
POST /auth/register
```json
{
  "username": "testuser",
  "email": "test@example.com",
  "password": "password123"
}
```
Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 2. Login User
POST /auth/login
```json
{
  "email": "test@example.com",
  "password": "password123"
}
```

### 3. Get Current User
GET /auth/me
Response:
```json
{
  "id": "...",
  "username": "testuser",
  "email": "test@example.com"
}
```

---

## TASKS (Date-Based System)

### 4. Get All Tasks (with filters)
GET /tasks/?due_date=2026-02-08&category=daily

Parameters:
- `due_date` (optional): Filter by specific date YYYY-MM-DD
- `category` (optional): Filter by category - "daily", "weekly", "monthly"

### 5. Get Today's Tasks
GET /tasks/today
Response:
```json
[
  {
    "id": "...",
    "title": "Submit Report",
    "description": "Finish the report",
    "due_date": "2026-02-08",
    "category": "daily",
    "is_completed": false,
    "completed_at": null,
    "user_id": "...",
    "created_at": "2026-02-08T10:00:00",
    "updated_at": "2026-02-08T10:00:00"
  }
]
```

### 6. Get Schedule (All tasks grouped by date)
GET /tasks/schedule?start_date=2026-02-01&end_date=2026-02-28
Response:
```json
{
  "schedule": {
    "2026-02-08": [
      {
        "id": "...",
        "title": "Task 1",
        "due_date": "2026-02-08",
        "category": "daily",
        "is_completed": false
      }
    ],
    "2026-02-10": [
      {
        "id": "...",
        "title": "Task 2",
        "due_date": "2026-02-10",
        "category": "weekly",
        "is_completed": false
      }
    ]
  },
  "total_tasks": 2
}
```

### 7. Create Task (Auto-categorized by due_date)
POST /tasks/
```json
{
  "title": "Complete project",
  "description": "Finish the backend API",
  "due_date": "2026-02-08"
}
```
Response:
```json
{
  "id": "...",
  "title": "Complete project",
  "description": "Finish the backend API",
  "due_date": "2026-02-08",
  "category": "daily",  // Auto-categorized: daily=weekly=monthly
  "is_completed": false,
  "completed_at": null,
  "user_id": "...",
  "created_at": "2026-02-08T10:00:00",
  "updated_at": "2026-02-08T10:00:00"
}
```

**Category Rules:**
- `due_date` = today → **daily**
- `due_date` within 7 days → **weekly**
- `due_date` > 7 days → **monthly**

### 8. Update Task
PUT /tasks/{task_id}
```json
{
  "title": "Updated title",
  "due_date": "2026-02-10"
}
```

### 9. Complete Task (Only on due_date!)
PATCH /tasks/{task_id}/complete

**Note:** Task can only be completed on its due_date!
If due_date != today, returns error:
```json
{
  "detail": "Task can only be completed on its due date (2026-02-10), not today"
}
```

### 10. Delete Task
DELETE /tasks/{task_id}

---

## HABITS

### 11. Get All Habits
GET /habits/
Response includes `completedToday` and `missedToday` status.

### 12. Create Habit
POST /habits/
```json
{
  "name": "Morning Exercise",
  "description": "30 minutes workout",
  "frequency": "daily"
}
```

### 13. Log Habit (Complete for Today)
POST /habits/{habit_id}/log
```json
{
  "completed": true,
  "notes": "Great workout!"
}
```
Creates ONE log per habit per day (updates if exists).

### 14. Mark Habit as Missed
POST /habits/{habit_id}/missed
Resets streak to 0.

### 15. Get Habit Analysis
GET /habits/{habit_id}/analysis

### 16. Get AI Prediction
GET /habits/{habit_id}/ai/predict

---

## AI COACH

### 17. Get Coach Status
GET /ai/coach/status
Response:
```json
{
  "status": "active",
  "coach_type": "Discipline Coach",
  "user_level": "Beginner",
  "summary": {
    "productivity_score": 72.5,
    "trend": "improving",
    "total_habits": 3,
    "average_streak": 5.2
  }
}
```

### 18. Get Tomorrow's Prediction
GET /ai/coach/tomorrow
Response:
```json
{
  "date": "2026-02-09",
  "overall_prediction": {
    "success_probability": 75.0,
    "level": "likely"
  },
  "habits_prediction": [
    {
      "habit_id": "...",
      "habit_name": "Morning Exercise",
      "success_probability": 80.0,
      "prediction": "likely",
      "risk_level": "low"
    }
  ],
  "alerts": []
}
```

### 19. Get All AI Insights
GET /ai/coach/insights
Response includes behavior analysis, habit predictions, and recommendations.

---

## SETTINGS

### 20. Change Password
PUT /settings/password
```json
{
  "current_password": "oldpassword",
  "new_password": "newpassword123"
}
```

### 21. Get Personalization
GET /settings/personalization

### 22. Update Personalization
PUT /settings/personalization

### 23. Get Profile
GET /settings/profile

### 24. Update Profile
PUT /settings/profile
```json
{
  "username": "newname",
  "email": "newemail@example.com"
}
```

---

## ERROR RESPONSES

### 401 Unauthorized
```json
{
  "detail": "Not authenticated"
}
```

### 400 Bad Request
```json
{
  "detail": "Task can only be completed on its due date (2026-02-10), not today"
}
```

### 404 Not Found
```json
{
  "detail": "Task not found"
}
```

### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["body", "due_date"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## DATA MODELS

### Task
| Field | Type | Description |
|-------|------|-------------|
| id | string | Task ID |
| title | string | Task title |
| description | string | Optional description |
| due_date | date | Due date (YYYY-MM-DD) |
| category | string | Auto-categorized: daily/weekly/monthly |
| is_completed | boolean | Completion status |
| completed_at | datetime | When completed |
| user_id | string | Owner ID |
| created_at | datetime | Creation time |
| updated_at | datetime | Last update time |

### Habit
| Field | Type | Description |
|-------|------|-------------|
| id | string | Habit ID |
| name | string | Habit name |
| description | string | Optional description |
| frequency | string | daily/weekly/etc |
| current_streak | int | Current streak |
| longest_streak | int | Longest streak |
| completedToday | boolean | Completed today? |
| missedToday | boolean | Missed today? |
| user_id | string | Owner ID |

### HabitLog
| Field | Type | Description |
|-------|------|-------------|
| _id | ObjectId | Log ID |
| habit_id | string | Habit ID |
| user_id | string | User ID |
| completed_date | datetime | Date completed |
| completed | boolean | Completion status |
| notes | string | Optional notes |
