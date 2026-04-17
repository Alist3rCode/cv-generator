"""
database.py — Configuration PostgreSQL + session SQLAlchemy
CV Generator App
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# URL de base de données :
#   - En production (Docker) : DATABASE_URL ou PostgreSQL via POSTGRES_PASSWORD
#   - En développement local  : SQLite (fallback si ni DATABASE_URL ni POSTGRES_PASSWORD)
_pw = os.getenv("POSTGRES_PASSWORD")
if os.getenv("DATABASE_URL"):
    DATABASE_URL = os.getenv("DATABASE_URL")
elif _pw:
    DATABASE_URL = f"postgresql+psycopg2://cvgen:{_pw}@db:5432/cvgen"
else:
    DATABASE_URL = "sqlite:///./cv_generator.db"

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)

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
