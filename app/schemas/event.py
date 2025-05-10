from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from enum import Enum

from app.schemas.department import Department
from app.schemas.program import Program
from app.schemas.user import SSGProfile
from app.schemas.attendance import Attendance
from pydantic import computed_field  # Add this import at the top

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

class EventUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    location: Optional[str] = Field(None, min_length=1, max_length=200)
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    status: Optional[EventStatus] = None
    department_ids: Optional[List[int]] = None
    program_ids: Optional[List[int]] = None
    ssg_member_ids: Optional[List[int]] = None

class Event(EventBase):
    id: int
    departments: List[Department] = Field(default_factory=list)
    programs: List[Program] = Field(default_factory=list)
    ssg_members: List[SSGProfile] = Field(default_factory=list)
    
    # Computed fields for IDs
    @computed_field
    def department_ids(self) -> List[int]:
        return [dept.id for dept in self.departments]
    
    @computed_field
    def program_ids(self) -> List[int]:
        return [program.id for program in self.programs]
    
    @computed_field
    def ssg_member_ids(self) -> List[int]:
        return [ssg.id for ssg in self.ssg_members]
    
    model_config = ConfigDict(from_attributes=True)

class EventWithRelations(Event):
    departments: List[Department] = Field(default_factory=list)
    programs: List[Program] = Field(default_factory=list)
    ssg_members: List[SSGProfile] = Field(
        default_factory=list,
        description="Assigned SSG members details"
    )
    attendances: List[Attendance] = Field(
        default_factory=list,
        description="Attendance records for this event"
    )
    attendance_summary: dict = Field(
        default_factory=dict,
        description="Counts by attendance status"
    )
    
    model_config = ConfigDict(from_attributes=True)

class EventPaginated(BaseModel):
    total: int
    items: List[Event]
    skip: int
    limit: int