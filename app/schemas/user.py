from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from enum import Enum
from datetime import datetime
from app.schemas.role import Role
from app.schemas.attendance import Attendance

class RoleEnum(str, Enum):
    student = "student"
    ssg = "ssg"
    event_organizer = "event-organizer"
    admin = "admin"

class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    middle_name: Optional[str] = None
    last_name: str

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    roles: List[RoleEnum]

# Add these base classes
class StudentProfileBase(BaseModel):
    student_id: str = Field(..., min_length=3)
    department_id: int
    program_id: int
    year_level: int = Field(ge=1, le=5, description="Year level must be between 1 and 5")  # Add this


class SSGProfileBase(BaseModel):
    position: str = Field(..., min_length=2)

# Create schemas (moved before classes that reference them)
class StudentProfileCreate(StudentProfileBase):
    pass

class SSGProfileCreate(SSGProfileBase):
    pass

class UserRoleResponse(BaseModel):
    role: 'Role'
    
    class Config:
        from_attributes = True

class StudentProfile(StudentProfileBase):
    id: int
    attendances: List[Attendance] = []
    
    class Config:
        from_attributes = True

class SSGProfile(SSGProfileBase):
    id: int
    
    class Config:
        from_attributes = True

class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    roles: List[UserRoleResponse] = []
    
    class Config:
        from_attributes = True

class UserWithRelations(User):
    student_profile: Optional[StudentProfile] = None
    ssg_profile: Optional[SSGProfile] = None