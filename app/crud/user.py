from sqlalchemy.orm import Session
from app.models.user import User as UserModel

def get_user(db: Session, user_id: str):
    """Get a user by ID."""
    return db.query(UserModel).filter(UserModel.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    """Get a user by email."""
    return db.query(UserModel).filter(UserModel.email == email).first()

def get_users(db: Session, skip: int = 0, limit: int = 100):
    """Get multiple users with pagination."""
    return db.query(UserModel).offset(skip).limit(limit).all()
