from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional
from enum import Enum

class AttendanceMethod(str, Enum):
    FACE_SCAN = "face_scan"
    MANUAL_ENTRY = "manual_entry"

class AttendanceBase(BaseModel):
    event_id: int = Field(..., gt=0)
    time_in: datetime  # Should be in base since it's required
    method: AttendanceMethod  # Using Enum instead of regex

class AttendanceCreate(AttendanceBase):
    pass

class Attendance(AttendanceBase):
    id: int = Field(..., gt=0)
    student_id: int = Field(..., gt=0)
    time_out: Optional[datetime] = None
    verified_by: Optional[int] = Field(None, gt=0)
    
    @field_validator('time_out')
    def validate_time_out(cls, v, values):
        if v and v < values.data['time_in']:
            raise ValueError("time_out must be after time_in")
        return v
    
    class Config:
        from_attributes = True
        use_enum_values = True  # Serializes enum to their values