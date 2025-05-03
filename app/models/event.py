from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
from app.models.base import Base
from app.models.associations import event_department_association, event_program_association, event_ssg_association

class EventStatus(PyEnum):
    UPCOMING = "upcoming"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class Event(Base):
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    location = Column(String(200))
    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime, nullable=False)
    status = Column(Enum(EventStatus), nullable=False, default=EventStatus.UPCOMING)
    
    # Many-to-many relationships
    departments = relationship(
        "Department", 
        secondary=event_department_association, 
        back_populates="events",
        lazy="joined"
    )
    programs = relationship(
        "Program", 
        secondary=event_program_association, 
        back_populates="events",
        lazy="joined"
    )
     # Add this relationship
    ssg_members = relationship(
        "SSGProfile", 
        secondary=event_ssg_association,
        back_populates="assigned_events",
        lazy="joined"
    )