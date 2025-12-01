# FocusForge API Documentation

## Base URL
http://localhost:8000/api/v1

## Authentication
All protected endpoints require JWT token in header:
Authorization: Bearer {your_jwt_token}

## Request/Response Examples

### 1. Register User
Request:
POST /auth/register
{
  "username": "testuser",
  "email": "test@example.com",
  "password": "password123"
}

Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}

### 2. Login User
Request:
POST /auth/login
{
  "email": "test@example.com",
  "password": "password123"
}

Response: Same as register

### 3. Create Task
Request:
POST /tasks/
{
  "title": "Complete project",
  "description": "Finish the backend API",
  "priority": "high"
}

Response:
{
  "title": "Complete project",
  "description": "Finish the backend API",
  "priority": "high",
  "status": "pending",
  "due_date": null,
  "user_id": "692c9359ee3ad50bcc395506",
  "created_at": "2025-12-01T16:23:24.169317",
  "updated_at": "2025-12-01T16:23:24.169320"
}

### 4. Create Habit
Request:
POST /habits/
{
  "name": "Morning Exercise",
  "description": "30 minutes workout",
  "frequency": "daily",
  "target_count": 1
}

Response:
{
  "name": "Morning Exercise",
  "description": "30 minutes workout",
  "frequency": "daily",
  "target_count": 1,
  "current_streak": 0,
  "longest_streak": 0,
  "user_id": "692c9359ee3ad50bcc395506",
  "created_at": "2025-12-01T16:25:10.123456",
  "is_active": true
}

## Error Responses

### 401 Unauthorized
{
  "detail": "Not authenticated"
}

### 403 Forbidden
{
  "detail": "Invalid token"
}

### 404 Not Found
{
  "detail": "Task not found"
}

### 422 Validation Error
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
