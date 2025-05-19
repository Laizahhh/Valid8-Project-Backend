# app/schemas/attendance.py
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum
from fastapi import Query
from sqlalchemy import func, case

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


class StudentAttendanceRecord(BaseModel):
    id: int
    event_id: int
    event_name: str  # We'll add this from the event model
    time_in: datetime
    time_out: Optional[datetime] = None
    status: AttendanceStatus
    method: AttendanceMethod
    notes: Optional[str] = None
    duration_minutes: Optional[int] = None  # Calculated field

    class Config:
        from_attributes = True

class StudentAttendanceResponse(BaseModel):
    student_id: str
    student_name: str
    total_records: int
    attendances: List[StudentAttendanceRecord]    

class AttendanceReportResponse(BaseModel):
    event_name: str
    event_date: str
    event_location: str
    total_participants: int
    attendees: int
    absentees: int
    attendance_rate: float
    programs: List[Dict[str, str]]  # For program filter dropdown
    program_breakdown: List[Dict[str, str]]  # For program-specific stats