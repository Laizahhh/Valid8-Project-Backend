# Reorder your classes in app/schemas/user.py:

from pydantic import BaseModel, EmailStr, Field, validator
from typing import List, Optional, ForwardRef
from enum import Enum
from datetime import datetime
from app.schemas.role import Role
from app.schemas.attendance import Attendance

class RoleEnum(str, Enum):
    student = "student"
    ssg = "ssg"
    event_organizer = "event-organizer"
    admin = "admin"

class SSGPositionEnum(str, Enum):
    PRESIDENT = "President"
    VICE_PRESIDENT = "Vice President"
    SECRETARY = "Secretary"
    TREASURER = "Treasurer"
    AUDITOR = "Auditor"
    PIO = "Public Information Officer"
    REPRESENTATIVE = "Representative"
    OTHER = "Other"

# Base classes first
class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    middle_name: Optional[str] = None
    last_name: str

class StudentProfileBase(BaseModel):
    student_id: Optional[str] = Field(
        None,
        min_length=3,
        max_length=20,
        pattern=r"^[A-Za-z0-9-]+$",
        example="CS-2023-001",
        description="Official student ID following format: [DepartmentCode]-[Year]-[SequenceNumber]"
    )
    department_id: Optional[int] = Field(
        None,
        description="ID of the department the student belongs to"
    )
    program_id: Optional[int] = Field(
        None,
        description="ID of the academic program the student is enrolled in"
    )
    year_level: Optional[int] = Field(
        None,
        ge=1,
        le=5,
        description="Year level must be between 1 and 5"
    )

class SSGProfileBase(BaseModel):
    position: SSGPositionEnum = Field(
        ...,
        description="Standardized SSG position title",
        example="President"
    )

# Create and update schemas
class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    roles: List[RoleEnum]

class UserUpdate(BaseModel):
    """Schema for partially updating user information"""
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None

class StudentProfileCreate(StudentProfileBase):
    user_id: int = Field(
        ...,
        description="The ID of the user to be assigned as a student"
    )

    @validator('student_id')
    def validate_student_id_format(cls, v):
        """Additional validation for student ID format"""
        if not any(char.isalpha() for char in v):
            raise ValueError("Student ID must contain at least one letter")
        if not any(char.isdigit() for char in v):
            raise ValueError("Student ID must contain at least one number")
        return v.upper()

class SSGProfileCreate(SSGProfileBase):
    user_id: int = Field(..., description="The ID of the user to be assigned as an SSG officer")

    @validator('position', pre=True)
    def validate_position(cls, v):
        if isinstance(v, str):
            v = v.strip().title()
            try:
                return SSGPositionEnum(v)
            except ValueError:
                variations = {
                    "VP": SSGPositionEnum.VICE_PRESIDENT,
                    "V.P.": SSGPositionEnum.VICE_PRESIDENT,
                    "P.R.O.": SSGPositionEnum.PIO
                }
                if v in variations:
                    return variations[v]
                raise ValueError(
                    f"Invalid position. Valid options: {[e.value for e in SSGPositionEnum]}"
                )
        return v

# For password reset/change
class PasswordUpdate(BaseModel):
    password: str = Field(
        ..., 
        min_length=8,
        description="New password"
    )
    
    @validator('password')
    def validate_password_strength(cls, v):
        """Validate password has minimum strength requirements"""
        if not any(char.isdigit() for char in v):
            raise ValueError("Password must contain at least one number")
        if not any(char.isupper() for char in v):
            raise ValueError("Password must contain at least one uppercase letter")
        return v

# For updating user roles
class UserRoleUpdate(BaseModel):
    roles: List[RoleEnum] = Field(
        ...,
        description="List of roles to assign to the user"
    )

# For bulk operations (optional)
class UserIdList(BaseModel):
    """Schema for bulk operations on users"""
    user_ids: List[int] = Field(
        ...,
        min_items=1,
        description="List of user IDs for bulk operations"
    )

# For filtering users (optional)
class UserFilter(BaseModel):
    """Optional schema for advanced user filtering"""
    department_id: Optional[int] = None
    program_id: Optional[int] = None
    year_level: Optional[int] = None
    role: Optional[RoleEnum] = None
    is_active: Optional[bool] = None

# Use forward references for circular dependencies
UserRef = ForwardRef('User')

class UserRoleResponse(BaseModel):
    role: Role
    
    class Config:
        from_attributes = True

class StudentProfile(StudentProfileBase):
    id: int
    attendances: List[Attendance] = []
    
    class Config:
        from_attributes = True

class SSGProfile(SSGProfileBase):
    id: int
    user: UserRef  # Using the forward reference
    
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

# Resolve forward references
SSGProfile.update_forward_refs()