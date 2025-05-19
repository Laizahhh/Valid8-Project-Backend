# app/models/attendance.py
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
from app.models.base import Base
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

class AttendanceStatus(PyEnum):
    PRESENT = "present"  # Must match database exactly
    ABSENT = "absent"
    EXCUSED = "excused"

def utc_now():
    return datetime.now(timezone.utc)


class Attendance(Base):
    __tablename__ = "attendances"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), index=True)
    time_in = Column(DateTime, nullable=False, default=datetime.utcnow)
    time_out = Column(DateTime)
    method = Column(String(50))  # "face_scan", "manual", etc.
    status = Column(
        PG_ENUM(
            'present', 'absent', 'excused',  # Explicit lowercase values
            name='attendancestatus',
            create_type=False  # Use existing type
        ),
        default='present',  # Lowercase default
        nullable=False
    )
    verified_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))  # Who verified (SSG/admin)
    notes = Column(String(500))  # Reason for excused absence, etc.

    # Relationships
    student = relationship("StudentProfile", back_populates="attendances")
    event = relationship("Event")