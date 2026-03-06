from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
from apscheduler.schedulers.background import BackgroundScheduler
import logging, os

from app.database import init_db
from app.routes import task_routes, habit_routes, auth_routes, settings_routes, ai_routes
from app.scheduler.habit_scheduler import run_daily_habit_check
from app.scheduler.task_scheduler import auto_mark_missed_tasks

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="FocusForge API", version="1.0.0")

os.makedirs("uploads/avatars", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    # "https://your-app.vercel.app",  # add when deployed
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Fix Cross-Origin-Opener-Policy to allow Google OAuth popup
@app.middleware("http")
async def add_coop_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cross-Origin-Opener-Policy"] = "unsafe-none"
    response.headers["Cross-Origin-Embedder-Policy"] = "unsafe-none"
    return response

app.include_router(auth_routes, prefix="/api/v1")
app.include_router(task_routes, prefix="/api/v1")
app.include_router(habit_routes, prefix="/api/v1")
app.include_router(settings_routes, prefix="/api/v1")
app.include_router(ai_routes, prefix="/api/v1")

scheduler = BackgroundScheduler(timezone="UTC")
scheduler.add_job(run_daily_habit_check, trigger="cron", hour=0, minute=0, id="daily_habit_enforcer", replace_existing=True)
scheduler.add_job(auto_mark_missed_tasks, trigger="cron", hour=1, minute=0, id="daily_task_missed_marker", replace_existing=True)

@app.on_event("startup")
async def startup_event():
    await init_db()
    scheduler.start()
    logger.info("✅ FocusForge backend ready")

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()

@app.get("/")
async def root():
    return {"message": "FocusForge Backend Running", "status": "healthy"}