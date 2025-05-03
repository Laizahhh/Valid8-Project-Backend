from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List
import os

from app.schemas.user import (
    UserCreate,
    User,
    UserWithRelations,
    StudentProfileCreate,  # Now properly imported
    SSGProfileCreate      # Now properly imported
)
from app.schemas.attendance import AttendanceCreate
from app.models.user import User as UserModel, UserRole, StudentProfile, SSGProfile
from app.models.role import Role
from app.models.attendance import Attendance
from app.services.face_recognition import FaceRecognitionService
from app.database import get_db
from app.core.security import create_access_token, get_current_user
from sqlalchemy.orm import joinedload

router = APIRouter(prefix="/users", tags=["users"])
face_service = FaceRecognitionService()

@router.post("/", response_model=User)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    # Check if email exists
    if db.query(UserModel).filter(UserModel.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    db_user = UserModel(
        email=user.email,
        first_name=user.first_name,
        middle_name=user.middle_name,
        last_name=user.last_name
    )
    db_user.set_password(user.password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Assign roles
    for role_name in user.roles:
        role = db.query(Role).filter(Role.name == role_name.value).first()
        if not role:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"Role '{role_name.value}' does not exist in database"
            )
        db.add(UserRole(user_id=db_user.id, role_id=role.id))
    
    db.commit()
    return User.from_orm(db_user)

@router.post("/students/", response_model=UserWithRelations)
def create_student_profile(
    profile: StudentProfileCreate,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not any(role.role.name == "student" for role in current_user.roles):
        raise HTTPException(status_code=403, detail="User is not a student")
    
    student_profile = StudentProfile(
        user_id=current_user.id,
        student_id=profile.student_id,
        department_id=profile.department_id,
        program_id=profile.program_id,
        year_level=profile.year_level  # Add this
    )
    db.add(student_profile)
    db.commit()
    db.refresh(current_user)
    return UserWithRelations.from_orm(current_user)

# ... rest of your routes with similar pattern ...
# Register face for student
@router.post("/students/register-face")
async def register_face(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.student_profile:
        raise HTTPException(status_code=403, detail="User is not a student")
    
    # Save uploaded file temporarily
    temp_path = f"temp_{current_user.id}.jpg"
    with open(temp_path, "wb") as buffer:
        buffer.write(await file.read())
    
    # Register face
    success = face_service.register_face(current_user.student_profile.student_id, temp_path)
    
    # Clean up
    os.remove(temp_path)
    
    if not success:
        raise HTTPException(status_code=400, detail="Face registration failed")
    
    return {"message": "Face registered successfully"}

# Attendance endpoints
@router.post("/attendance/face-scan")
async def face_scan_attendance(
    event_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Save uploaded file temporarily
    temp_path = f"temp_attendance_{current_user.id}.jpg"
    with open(temp_path, "wb") as buffer:
        buffer.write(await file.read())
    
    # Recognize face
    student_id = face_service.recognize_face(temp_path)
    os.remove(temp_path)
    
    if not student_id:
        raise HTTPException(status_code=400, detail="Face recognition failed")
    
    # Get student profile
    student = db.query(StudentProfile).filter(StudentProfile.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Record attendance
    attendance = Attendance(
        student_id=student.id,
        event_id=event_id,
        time_in=datetime.utcnow(),
        method="face_scan"
    )
    db.add(attendance)
    db.commit()
    
    return {"message": "Attendance recorded successfully"}

@router.post("/attendance/manual")
def manual_attendance(
    data: AttendanceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify user has student role
    if not any(role.role.name == "student" for role in current_user.roles):
        raise HTTPException(status_code=403, detail="User is not a student")
    
    if not current_user.student_profile:
        raise HTTPException(status_code=403, detail="Student profile not found")
    
    # Record attendance
    attendance = Attendance(
        student_id=current_user.student_profile.id,
        event_id=data.event_id,
        time_in=datetime.utcnow(),
        method=data.method
    )
    db.add(attendance)
    db.commit()
    
    return {"message": "Attendance recorded successfully"}

# SSG verification endpoint
@router.post("/attendance/verify/{attendance_id}")
def verify_attendance(
    attendance_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify user has SSG role
    if not any(role.role.name == "ssg" for role in current_user.roles):
        raise HTTPException(status_code=403, detail="User is not SSG")
    
    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    
    attendance.verified_by = current_user.id
    db.commit()
    
    return {"message": "Attendance verified successfully"}


@router.get("/", response_model=List[UserWithRelations])
def get_all_users(
    skip: int = 0, 
    limit: int = 100,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all users with pagination, including their profiles and roles.
    
    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return (for pagination)
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        List of users with all related data
    """
    # Optional permission check
    # if not any(role.role.name == "admin" for role in current_user.roles):
    #     raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Get users with eager loading of relationships
    users = db.query(UserModel).offset(skip).limit(limit).all()
    return [UserWithRelations.from_orm(user) for user in users]


@router.get("/by-role/{role_name}", response_model=List[UserWithRelations])
def get_users_by_role(
    role_name: str,
    skip: int = 0,
    limit: int = 100,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get users filtered by role.
    
    Args:
        role_name: Role name to filter by (student, ssg, admin, etc.)
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return (for pagination)
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        List of users with the specified role
    """
    # Find all users with the specified role
    users = (
        db.query(UserModel)
        .join(UserRole)
        .join(Role)
        .filter(Role.name == role_name)
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    return [UserWithRelations.from_orm(user) for user in users]


@router.post("/ssg-profile/", response_model=UserWithRelations)
def create_ssg_profile(
    profile: SSGProfileCreate,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create SSG profile for the authenticated user
    """
    # Check if user has SSG role
    if not any(role.role.name == "ssg" for role in current_user.roles):
        raise HTTPException(status_code=403, detail="User is not an SSG member")
    
    # Check if user already has SSG profile
    if current_user.ssg_profile:
        raise HTTPException(status_code=400, detail="User already has an SSG profile")
    
    # Create SSG profile
    ssg_profile = SSGProfile(
        user_id=current_user.id,
        position=profile.position
    )
    
    db.add(ssg_profile)
    db.commit()
    db.refresh(current_user)
    
    return UserWithRelations.from_orm(current_user)


@router.get("/me/", response_model=UserWithRelations)
def get_current_user_profile(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user with all profile information
    """
    # Refresh to ensure we have the latest data
    db.refresh(current_user)
    return UserWithRelations.from_orm(current_user)


@router.get("/ssg-members/", response_model=List[UserWithRelations])
def get_ssg_members(
    skip: int = 0,
    limit: int = 100,
    include_profiles: bool = True,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all users with SSG role, including their SSG profiles if available
    
    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        include_profiles: Whether to include SSG profile details
        current_user: Authenticated user
        db: Database session
        
    Returns:
        List of SSG members with their user data
    """
    # Base query for users with SSG role
    query = (
        db.query(UserModel)
        .join(UserRole)
        .join(Role)
        .filter(Role.name == "ssg")
        .order_by(UserModel.last_name)
    )
    
    # Eager load relationships if requested
    if include_profiles:
        query = query.options(
            joinedload(UserModel.roles).joinedload(UserRole.role),
            joinedload(UserModel.ssg_profile)
        )
    
    # Apply pagination
    ssg_members = query.offset(skip).limit(limit).all()
    
    return [UserWithRelations.from_orm(user) for user in ssg_members]