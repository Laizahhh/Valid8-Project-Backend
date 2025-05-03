# app/database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
import logging

# Configure logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:new_secure_password123!@localhost:5432/fastapi_db")

engine = create_engine(
    DATABASE_URL,
    echo=True,  # This will show SQL queries in console
    pool_pre_ping=True  # Checks connection before using
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
