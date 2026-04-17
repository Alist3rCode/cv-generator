"""
database.py — Configuration PostgreSQL + session SQLAlchemy
CV Generator App
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# URL PostgreSQL — construite depuis POSTGRES_PASSWORD ou surchargée via DATABASE_URL
_pw = os.getenv("POSTGRES_PASSWORD", "cvgen")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql+psycopg2://cvgen:{_pw}@db:5432/cvgen",
)

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dépendance FastAPI — fournit une session DB et la ferme après la requête."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Crée toutes les tables si elles n'existent pas."""
    from models import Base
    Base.metadata.create_all(bind=engine)
