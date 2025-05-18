# app/schemas/attendance.py
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional
from enum import Enum

class AttendanceMethod(str, Enum):
    FACE_SCAN = "face_scan"
    MANUAL = "manual"

class AttendanceStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    EXCUSED = "excused"

class AttendanceBase(BaseModel):
    event_id: int = Field(..., gt=0)
    time_in: datetime
    method: AttendanceMethod
    status: AttendanceStatus = Field(default=AttendanceStatus.PRESENT)

    @field_validator('status', mode='before')
    def validate_status(cls, v):
        if isinstance(v, str):
            return v.lower()  # Ensure lowercase
        return v
    
    class Config:
        use_enum_values = True
class AttendanceCreate(AttendanceBase):
    pass

class Attendance(AttendanceBase):
    id: int = Field(..., gt=0)
    student_id: int = Field(..., gt=0)
    time_out: Optional[datetime] = None
    verified_by: Optional[int] = Field(None, gt=0)
    notes: Optional[str] = None
    
    @field_validator('time_out')
    @classmethod
    def validate_time_out(cls, v, info):
        # Fixed: Use info.data instead of values.data
        if v and 'time_in' in info.data and v < info.data['time_in']:
            raise ValueError("time_out must be after time_in")
        return v
    
    class Config:
        from_attributes = True
        use_enum_values = True  # Serializes enum to their values

class AttendanceWithStudent(BaseModel):
    attendance: Attendance
    student_id: str
    student_name: str     