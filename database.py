"""
database.py — Configuration SQLite + session SQLAlchemy
CV Generator App
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

# Base de données SQLite locale (fichier cv_generator.db créé automatiquement)
DATABASE_URL = "sqlite:///./cv_generator.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Nécessaire pour SQLite avec FastAPI
)

# Activer les clés étrangères sur SQLite (désactivées par défaut)
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

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
