import uvicorn
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from apps.backend.database import get_db, Base, engine
from apps.backend.seed import seed_database
from apps.backend.routers.payments import router as payments_router
from apps.backend.routers.dashboard import router as dashboard_router
from apps.backend.config import settings

# Initialize database tables
Base.metadata.create_all(bind=engine)

# Seed database on startup if empty
db = SessionLocal = next(get_db())
try:
    seed_database(db)
finally:
    db.close()

app = FastAPI(
    title="RecoveryOS Backend & Simulator API",
    description="Autonomous Revenue Recovery Platform with policy guardrails.",
    version="1.0.0"
)

cors_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]

# Enable CORS for frontend dashboard development
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(payments_router)
app.include_router(dashboard_router)

@app.get("/")
def read_root():
    return {
        "status": "healthy",
        "service": "RecoveryOS API",
        "documentation": "/docs"
    }

@app.get("/health")
def health_check():
    """Minimal liveness endpoint for containers and deployment checks."""
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("apps.backend.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
