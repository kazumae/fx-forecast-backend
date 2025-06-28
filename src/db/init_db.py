from sqlalchemy.orm import Session

from src.db.session import engine
from src.models.base import Base
from src.models import user, forex  # Import all models

def init_db() -> None:
    # Create all tables
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")