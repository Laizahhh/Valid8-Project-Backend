# app/seeder.py
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models.base import Base
from app.models.role import Role

def create_tables():
    """Create all tables"""
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created")

def seed_roles(db: Session):
    """Seed roles table with required roles"""
    roles_data = [
        {"name": "student"},
        {"name": "ssg"},
        {"name": "event-organizer"},
        {"name": "admin"}
    ]
    
    existing_roles = db.query(Role).all()
    existing_role_names = {role.name for role in existing_roles}
    
    for role_data in roles_data:
        if role_data["name"] not in existing_role_names:
            role = Role(**role_data)
            db.add(role)
    
    db.commit()
    print("✅ Roles seeded")

def run_seeder():
    """Main seeder function"""
    print("🌱 Starting database seeding...")
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Create tables first
        create_tables()
        
        # Seed only roles
        seed_roles(db)
        
        print("🎉 Database seeding completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during seeding: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run_seeder()