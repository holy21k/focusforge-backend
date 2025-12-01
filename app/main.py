from fastapi import FastAPI
from app.database import init_db
from app.routes import task_routes, habit_routes, auth_routes

app = FastAPI(title="FocusForge API", version="1.0.0")

# Include routers
app.include_router(auth_routes, prefix="/api/v1")
app.include_router(task_routes, prefix="/api/v1")
app.include_router(habit_routes, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    await init_db()

@app.get("/")
async def root():
    return {"message": "FocusForge Backend Running", "status": "healthy"}
