# app/models/department.py
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.models.base import Base
from app.models.associations import program_department_association, event_department_association

class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

    # Relationships
    programs = relationship(
        "Program", 
        secondary=program_department_association,
        back_populates="departments",
        lazy="joined"  # Always load related programs
    )
    events = relationship(
        "Event",
        secondary=event_department_association,
        back_populates="departments",
        lazy="joined"  # Always load related events
    )