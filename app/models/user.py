from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime
import bcrypt
from typing import Optional
from app.models.associations import event_ssg_association

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100))
    middle_name = Column(String(100))
    last_name = Column(String(100))
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
    student_profile = relationship("StudentProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    ssg_profile = relationship("SSGProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    
    def set_password(self, password: str):
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt(rounds=12)
        ).decode('utf-8')
    
    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

class UserRole(Base):
    __tablename__ = "user_roles"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), index=True)
    
    user = relationship("User", back_populates="roles")
    role = relationship("Role")

class StudentProfile(Base):
    __tablename__ = "student_profiles"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    student_id = Column(String(50), unique=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="RESTRICT"), index=True)
    program_id = Column(Integer, ForeignKey("programs.id", ondelete="RESTRICT"), index=True)
    year_level = Column(Integer, nullable=False, default=1)  # Add this line
    face_encoding = Column(String(2000))  # Increased length for encoding storage
    
    user = relationship("User", back_populates="student_profile")
    attendances = relationship("Attendance", back_populates="student", cascade="all, delete-orphan")

class SSGProfile(Base):
    __tablename__ = "ssg_profiles"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    position = Column(String(100), index=True)
    
    user = relationship("User", back_populates="ssg_profile")
    assigned_events = relationship(  # Add this
        "Event",
        secondary=event_ssg_association,
        back_populates="ssg_members",
        lazy="joined"
    )