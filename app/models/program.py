# app/models/program.py
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.models.base import Base
from app.models.associations import program_department_association, event_program_association

class Program(Base):
    __tablename__ = "programs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

    # Relationships
    departments = relationship(
        "Department",
        secondary=program_department_association,
        back_populates="programs",
        lazy="joined"  # Always load departments
    )
    events = relationship(
        "Event",
        secondary=event_program_association,
        back_populates="programs",
        lazy="joined"  # Always load events
    )