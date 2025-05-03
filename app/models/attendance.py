from sqlalchemy import Column, Integer, DateTime, ForeignKey, Enum, String
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime

class Attendance(Base):
    __tablename__ = "attendances"
    
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("student_profiles.id"))
    event_id = Column(Integer, ForeignKey("events.id"))
    time_in = Column(DateTime)
    time_out = Column(DateTime)
    method = Column(String(50))  # Changed from Enum for simplicity
    verified_by = Column(Integer, ForeignKey("users.id"))
    
    student = relationship("StudentProfile", back_populates="attendances")
    event = relationship("Event")
    verifier = relationship("User")