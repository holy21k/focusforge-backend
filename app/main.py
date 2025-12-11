from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.routes import task_routes, habit_routes, auth_routes

app = FastAPI(title="FocusForge API", version="1.0.0")

# -----------------------------
# CORS FIX
# -----------------------------
origins = [
    "http://localhost:5173",   # Vite frontend
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # Allow frontend
    allow_credentials=True,
    allow_methods=["*"],         # Allow all methods
    allow_headers=["*"],         # Allow all headers
)

# -----------------------------
# ROUTES
# -----------------------------
app.include_router(auth_routes, prefix="/api/v1")
app.include_router(task_routes, prefix="/api/v1")
app.include_router(habit_routes, prefix="/api/v1")

# -----------------------------
# STARTUP EVENT
# -----------------------------
@app.on_event("startup")
async def startup_event():
    await init_db()

# -----------------------------
# ROOT ROUTE
# -----------------------------
@app.get("/")
async def root():
    return {"message": "FocusForge Backend Running", "status": "healthy"}

