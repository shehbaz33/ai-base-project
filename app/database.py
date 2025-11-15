from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config.settings import get_settings

# Get settings
settings = get_settings()

# Create database engine
engine = create_engine(
    settings.DATABASE_URL,  # This will call the DATABASE_URL property
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

def init_db():
    """Initialize database and create tables"""
    from app.models.user import Base  # Import your models
    Base.metadata.create_all(bind=engine)

def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
