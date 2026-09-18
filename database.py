"""
database.py
------------
Central place for the SQLAlchemy engine + session.

By default this runs on a local SQLite file (tastehub.db) so the project
works immediately with zero setup. To use real MySQL (as the spec asks
for), just set the DATABASE_URL environment variable, e.g.:

    export DATABASE_URL="mysql+pymysql://root:yourpassword@localhost:3306/tastehub"

Nothing else in the codebase needs to change - SQLAlchemy abstracts the
difference between SQLite and MySQL for everything we do here.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tastehub.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
