import pytest
from app.models import User, Role, UserRole
from sqlalchemy.exc import IntegrityError

# Test user creation
def test_user_creation(test_db):
    # Create test data
    role = Role(name="admin")
    test_db.add(role)
    test_db.commit()
    
    user = User(
        email="test@example.com",
        first_name="Test",
        last_name="User"
    )
    user.set_password("SecurePassword123!")
    test_db.add(user)
    test_db.commit()
    
    # Create user role association
    user_role = UserRole(user_id=user.id, role_id=role.id)
    test_db.add(user_role)
    test_db.commit()
    
    # Verify
    assert user.id is not None
    assert user.check_password("SecurePassword123!") is True
    assert not user.check_password("WrongPassword")
    
    # Test relationship loading
    user_with_roles = test_db.query(User).filter(User.id == user.id).first()
    assert len(user_with_roles.roles) == 1
    assert user_with_roles.roles[0].role.name == "admin"

# Test email uniqueness constraint
def test_email_uniqueness(test_db):
    # Create first user
    user1 = User(
        email="duplicate@example.com",
        first_name="First",
        last_name="User"
    )
    user1.set_password("password123")
    test_db.add(user1)
    test_db.commit()
    
    # Try to create second user with same email
    user2 = User(
        email="duplicate@example.com",
        first_name="Second",
        last_name="User"
    )
    user2.set_password("password456")
    test_db.add(user2)
    
    # Should raise integrity error
    with pytest.raises(IntegrityError):
        test_db.commit()
    
    # Rollback after error
    test_db.rollback()

# Test password hashing
def test_password_hashing(test_db):
    user = User(
        email="security@example.com",
        first_name="Security",
        last_name="Test"
    )
    
    # Set and check password
    test_password = "SuperSecurePassword123!"
    user.set_password(test_password)
    
    # Password should be hashed, not stored in plain text
    assert user.hashed_password != test_password
    assert user.check_password(test_password) is True
    assert user.check_password("WrongPassword") is False

# For running directly without pytest
if __name__ == "__main__":
    from app.database import SessionLocal
    import os
    
    def manual_test():
        # Get database URL from environment or use default
        db_url = os.environ.get(
            "TEST_DATABASE_URL", 
            "postgresql://postgres:postgres@localhost:5432/test_db"
        )
        
        print(f"Running manual test with database: {db_url}")
        db = SessionLocal()
        
        try:
            # Create test data
            role = Role(name="admin")
            db.add(role)
            db.commit()
            
            user = User(
                email="test@example.com",
                first_name="Test",
                last_name="User"
            )
            user.set_password("SecurePassword123!")
            db.add(user)
            db.commit()
            
            # Create user role association
            user_role = UserRole(user_id=user.id, role_id=role.id)
            db.add(user_role)
            db.commit()
            
            # Verify
            assert user.id is not None
            assert user.check_password("SecurePassword123!") is True
            
            print("✅ All tests passed!")
        except Exception as e:
            print(f"❌ Test failed: {e}")
        finally:
            db.rollback()
            db.close()
    
    manual_test()