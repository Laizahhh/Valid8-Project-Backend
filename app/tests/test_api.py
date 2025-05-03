import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app  # Import your FastAPI app
from app.models import User, Role, UserRole
from app.core.security import create_access_token

# Create a test client
client = TestClient(app)

# Test user creation API
def test_create_user_api():
    response = client.post(
        "/users/",
        json={
            "email": "apitest@example.com",
            "password": "StrongPassword123!",
            "first_name": "API",
            "middle_name": "",
            "last_name": "Test",
            "roles": ["student"]
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "apitest@example.com"
    assert data["first_name"] == "API"
    assert data["last_name"] == "Test"

# Test user authentication
def test_user_authentication(test_db):
    # Create a user
    user = User(
        email="auth@example.com",
        first_name="Auth",
        last_name="Test"
    )
    user.set_password("AuthPassword123!")
    test_db.add(user)
    test_db.commit()
    
    # Test login with valid credentials
    response = client.post(
        "/auth/login",  # Adjust to your actual login endpoint
        data={
            "username": "auth@example.com",  # Using email as username
            "password": "AuthPassword123!"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    
    # Test login with invalid password
    response = client.post(
        "/auth/login",  # Adjust to your actual login endpoint
        data={
            "username": "auth@example.com",
            "password": "WrongPassword"
        }
    )
    assert response.status_code == 401

# Test protected endpoint
def test_protected_endpoint(test_db):
    # Create a user with student role
    role = Role(name="student")
    test_db.add(role)
    test_db.commit()
    
    user = User(
        email="student@example.com",
        first_name="Student",
        last_name="Test"
    )
    user.set_password("StudentPass123!")
    test_db.add(user)
    test_db.commit()
    
    user_role = UserRole(user_id=user.id, role_id=role.id)
    test_db.add(user_role)
    test_db.commit()
    
    # Create access token
    token = create_access_token({"sub": user.email})
    
    # Test access to protected endpoint
    response = client.post(
        "/users/students/",  # Adjust to your actual endpoint
        headers={"Authorization": f"Bearer {token}"},
        json={
            "student_id": "2023001",
            "department_id": 1,
            "program_id": 1
        }
    )
    assert response.status_code == 200
    
    # Test access without token
    response = client.post(
        "/users/students/",
        json={
            "student_id": "2023002",
            "department_id": 1,
            "program_id": 1
        }
    )
    assert response.status_code == 401  # Unauthorized