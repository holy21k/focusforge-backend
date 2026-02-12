from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from app.database import init_db
from app.routes import task_routes, habit_routes, auth_routes, settings_routes, ai_routes
from app.scheduler.habit_scheduler import run_daily_habit_check
from app.scheduler.task_scheduler import auto_mark_missed_tasks

# --------------------------------------------------
# APP INIT
# --------------------------------------------------
app = FastAPI(title="FocusForge API", version="1.0.0")

# --------------------------------------------------
# CORS
# --------------------------------------------------
origins = [
    "http://localhost:3000",   # React dev server
    "http://127.0.0.1:3000",
    "http://localhost:5173",   # Vite frontend (if any)
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # allows GET, POST, OPTIONS, etc.
    allow_headers=["*"],  # allows Content-Type, Authorization, etc.
)

# --------------------------------------------------
# ROUTES
# --------------------------------------------------
app.include_router(auth_routes, prefix="/api/v1")
app.include_router(task_routes, prefix="/api/v1")
app.include_router(habit_routes, prefix="/api/v1")
app.include_router(settings_routes, prefix="/api/v1")
app.include_router(ai_routes, prefix="/api/v1")

# --------------------------------------------------
# SCHEDULER (CORE SYSTEM ENGINE)
# --------------------------------------------------
scheduler = BackgroundScheduler(timezone="UTC")

scheduler.add_job(
    run_daily_habit_check,
    trigger="cron",
    hour=0,
    minute=0,
    id="daily_habit_enforcer",
    replace_existing=True
)

scheduler.add_job(
    auto_mark_missed_tasks,
    trigger="cron",
    hour=1,
    minute=0,
    id="daily_task_missed_marker",
    replace_existing=True
)

# --------------------------------------------------
# STARTUP / SHUTDOWN
# --------------------------------------------------
@app.on_event("startup")
async def startup_event():
    await init_db()
    scheduler.start()
    print("✅ Scheduler started")
    print("✅ FocusForge backend ready")

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()
    print("🛑 Scheduler stopped")

# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------
@app.get("/")
async def root():
    return {
        "message": "FocusForge Backend Running",
        "status": "healthy",
        "scheduler": "active"
    }
