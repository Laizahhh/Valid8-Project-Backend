import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy_utils import database_exists, create_database, drop_database
from dotenv import load_dotenv

# Load environment variables from .env.test
load_dotenv(".env.test")

from app.database import Base
from app.models import User, Role, UserRole

# PostgreSQL test database URL - Use environment variables 
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", 
    "postgresql://postgres:postgres@localhost:5432/test_db"
)

@pytest.fixture(scope="session")
def test_engine():
    """Create a test database and return the engine."""
    # Create the test database if it doesn't exist
    if not database_exists(TEST_DATABASE_URL):
        create_database(TEST_DATABASE_URL)
    
    engine = create_engine(TEST_DATABASE_URL)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Drop the test database after all tests
    drop_database(TEST_DATABASE_URL)

@pytest.fixture(scope="function")
def test_db(test_engine):
    """Create a fresh session for each test."""
    # Create a new session for each test
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = TestingSessionLocal()
    
    try:
        yield db
    finally:
        # Roll back at the end of each test
        db.rollback()
        db.close()
        
        # Clear all tables for isolation between tests
        for table in reversed(Base.metadata.sorted_tables):
            test_engine.execute(table.delete())

@pytest.fixture
def test_user(test_db):
    """Create a test user with admin role."""
    role = Role(name="admin")
    test_db.add(role)
    test_db.commit()
    
    user = User(
        email="test@example.com",
        first_name="Test",
        last_name="User"
    )
    user.set_password("password123")
    test_db.add(user)
    test_db.commit()
    
    user_role = UserRole(user_id=user.id, role_id=role.id)
    test_db.add(user_role)
    test_db.commit()
    
    return user