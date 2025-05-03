from pydantic import BaseModel, EmailStr
from typing import List, Optional
from enum import Enum

class Token(BaseModel):
    access_token: str
    token_type: str
    email: Optional[str] = None
    roles: Optional[List[str]] = None
    user_id: Optional[int] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class TokenData(BaseModel):
    email: Optional[str] = None
    roles: Optional[List[str]] = None  # Added roles for better access control

class LoginRequest(BaseModel):
    email: EmailStr  # More strict validation
    password: str

class RoleEnum(str, Enum):
    admin = "admin"
    student = "student"
    ssg = "ssg"
    event_organizer = "event-organizer"  # Added missing role
    
    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    roles: List[RoleEnum]  # Now includes all possible roles