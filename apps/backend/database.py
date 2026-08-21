from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from apps.backend.config import settings

DATABASE_URL = settings.DATABASE_URL

# SQLite-specific arguments (allows multi-threaded database access)
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

try:
    engine = create_engine(DATABASE_URL, connect_args=connect_args)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as e:
    # If postgres fails, fall back to sqlite for demo stability
    print(f"Failed to connect to database {DATABASE_URL} due to: {e}. Falling back to SQLite.")
    sqlite_fallback_url = "sqlite:///./recoveryos.db"
    engine = create_engine(sqlite_fallback_url, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
