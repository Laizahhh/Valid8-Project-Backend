from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from enum import Enum
from app.schemas.department import Department
from app.schemas.program import Program
from app.schemas.user import SSGProfile  # Make sure to import SSGProfile

class EventStatus(str, Enum):
    upcoming = "upcoming"
    ongoing = "ongoing"
    completed = "completed"
    cancelled = "cancelled"

class EventBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    location: str = Field(..., min_length=1, max_length=200)
    start_datetime: datetime
    end_datetime: datetime
    status: EventStatus = EventStatus.upcoming

class EventCreate(EventBase):
    department_ids: List[int] = Field(default_factory=list)
    program_ids: List[int] = Field(default_factory=list)
    ssg_member_ids: List[int] = Field(
        default_factory=list,
        description="List of SSG profile IDs to assign to this event"
    )

class Event(EventBase):
    id: int
    department_ids: List[int] = Field(default_factory=list)
    program_ids: List[int] = Field(default_factory=list)
    ssg_member_ids: List[int] = Field(default_factory=list)
    
    model_config = ConfigDict(from_attributes=True)

class EventWithRelations(Event):
    departments: List[Department] = Field(default_factory=list)
    programs: List[Program] = Field(default_factory=list)
    ssg_members: List[SSGProfile] = Field(  # Changed from ssg_member_ids to ssg_members
        default_factory=list,
        description="Detailed info about assigned SSG members"
    )
    
    model_config = ConfigDict(from_attributes=True)