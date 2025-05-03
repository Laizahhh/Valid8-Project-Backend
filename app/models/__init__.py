# Import all models here so they can be imported elsewhere with a single import 
# The order of imports is important here - import base first
from app.models.base import Base
from app.models.department import Department
from app.models.program import Program
from app.models.event import Event

from .role import Role
from .user import User, UserRole, StudentProfile, SSGProfile
from .attendance import Attendance  # If you have this model

__all__ = ['Base', 'Role', 'User', 'UserRole', 'StudentProfile', 'SSGProfile', 'Attendance']