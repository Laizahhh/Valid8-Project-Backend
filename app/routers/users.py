from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List
import os
from app.core.security import get_current_user_with_roles  # Modified dependency
from app.models.department import Department
from app.models.program import Program
from sqlalchemy import select

from app.schemas.user import (
    UserCreate,
    User,
    UserWithRelations,
    StudentProfileCreate,
    SSGProfileCreate,
    SSGPositionEnum,
    UserUpdate,          # New import
    PasswordUpdate,      # New import
    UserRoleUpdate,      # New import
    StudentProfileBase,          # New import (if you're using it)
    SSGProfileBase           # New import (if you're using it)
)
from app.schemas.event import Event
from app.models.user import User as UserModel, UserRole, StudentProfile, SSGProfile
from app.models.role import Role
from app.models.attendance import Attendance
from app.services.face_recognition import FaceRecognitionService
from app.database import get_db
from app.core.security import create_access_token
from sqlalchemy.orm import joinedload
from app.models.associations import program_department_association

router = APIRouter(prefix="/users", tags=["users"])
face_service = FaceRecognitionService()

# Helper function to check if user has any of the required roles
def has_required_roles(user: UserModel, required_roles: List[str]) -> bool:
    """Check if user has any of the required roles"""
    user_roles = set(role.role.name for role in user.roles)
    return any(role in user_roles for role in required_roles)

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

@router.post("/admin/students/", response_model=UserWithRelations)
def create_student_profile(
    profile: StudentProfileCreate,
    current_user: UserModel = Depends(get_current_user_with_roles),
    db: Session = Depends(get_db)
):
    # Check if user has admin, ssg, or event-organizer role
    required_roles = ["admin", "ssg", "event-organizer"]
    if not has_required_roles(current_user, required_roles):
        raise HTTPException(
            status_code=403, 
            detail="Insufficient permissions. Requires admin, SSG or event-organizer role"
        )
    
    # 1. Verify target user exists
    target_user = db.get(UserModel, profile.user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")
    
    # 2. Verify student ID doesn't exist
    if db.query(StudentProfile).filter(StudentProfile.student_id == profile.student_id).first():
        raise HTTPException(status_code=400, detail="Student ID already in use")
    
    # 3. Verify department and program exist
    department = db.get(Department, profile.department_id)
    program = db.get(Program, profile.program_id)
    
    if not department or not program:
        raise HTTPException(status_code=400, detail="Invalid department or program ID")
    
    # 4. Verify program belongs to department (many-to-many check)
    association_exists = db.execute(
        select(program_department_association)
        .where(
            (program_department_association.c.department_id == department.id) &
            (program_department_association.c.program_id == program.id)
        )
    ).first()

    if not association_exists:
        raise HTTPException(
            status_code=400,
            detail=f"Program '{program.name}' is not offered by department '{department.name}'"
        )
    
    # 5. Create profile
    try:
        student_profile = StudentProfile(
            user_id=profile.user_id,
            student_id=profile.student_id,
            department_id=profile.department_id,
            program_id=profile.program_id,
            year_level=profile.year_level
        )
        
        db.add(student_profile)
        db.commit()
        db.refresh(target_user)
        
        return UserWithRelations.from_orm(target_user)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create student profile: {str(e)}"
        )


@router.get("/", response_model=List[UserWithRelations])
def get_all_users(
    skip: int = 0, 
    limit: int = 100,
    current_user: UserModel = Depends(get_current_user_with_roles),
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
    # Allow admin, SSG, or event-organizer to access all users
    required_roles = ["admin", "ssg", "event-organizer"]
    if not has_required_roles(current_user, required_roles):
        raise HTTPException(
            status_code=403, 
            detail="Insufficient permissions. Requires admin, SSG or event-organizer role"
        )
    
    # Get users with eager loading of relationships
    users = db.query(UserModel).offset(skip).limit(limit).all()
    return [UserWithRelations.from_orm(user) for user in users]


@router.get("/by-role/{role_name}", response_model=List[UserWithRelations])
def get_users_by_role(
    role_name: str,
    skip: int = 0,
    limit: int = 100,
    current_user: UserModel = Depends(get_current_user_with_roles),
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
    # Allow admin, SSG, or event-organizer to filter users by role
    required_roles = ["admin", "ssg", "event-organizer"]
    if not has_required_roles(current_user, required_roles):
        raise HTTPException(
            status_code=403, 
            detail="Insufficient permissions. Requires admin, SSG or event-organizer role"
        )
    
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

@router.get("/ssg-positions/", response_model=List[dict])
def get_ssg_position_types():
    """Get all valid SSG position types for dropdowns"""
    return [{"value": e.value, "label": e.value} for e in SSGPositionEnum]


@router.post("/ssg-profiles/", response_model=UserWithRelations)
def create_ssg_profile(
    profile: SSGProfileCreate,
    current_user: UserModel = Depends(get_current_user_with_roles),
    db: Session = Depends(get_db)
):
    """Create SSG profile endpoint with validated position"""
    required_roles = ["admin", "ssg", "event-organizer"]
    if not has_required_roles(current_user, required_roles):
        raise HTTPException(
            status_code=403, 
            detail="Insufficient permissions"
        )
    
    # Get the target user
    user = db.query(UserModel).get(profile.user_id)
    if not user:
        raise HTTPException(404, "User not found")
    
    # Verify SSG role exists
    if not any(role.role.name == "ssg" for role in user.roles):
        raise HTTPException(400, "User does not have SSG role")
    
    # Check for existing profile
    if user.ssg_profile:
        raise HTTPException(400, "User already has an SSG profile")
    
    # Create the profile (position is automatically validated by Pydantic)
    ssg_profile = SSGProfile(
        user_id=user.id,
        position=profile.position  # This is now an SSGPositionEnum value
    )
    
    db.add(ssg_profile)
    db.commit()
    db.refresh(user)
    return UserWithRelations.from_orm(user)


@router.get("/me/", response_model=UserWithRelations)
def get_current_user_profile(
    current_user: UserModel = Depends(get_current_user_with_roles),
    db: Session = Depends(get_db)
):
    """
    Get current user with all profile information
    """
    # Accessible to any authenticated user
    # Refresh to ensure we have the latest data
    db.refresh(current_user)
    return UserWithRelations.from_orm(current_user)


@router.get("/ssg-members/", response_model=List[UserWithRelations])
def get_ssg_members(
    skip: int = 0,
    limit: int = 100,
    include_profiles: bool = True,
    current_user: UserModel = Depends(get_current_user_with_roles),
    db: Session = Depends(get_db)
):
    """Get all SSG members with their positions"""
    query = (
        db.query(UserModel)
        .join(UserRole)
        .join(Role)
        .filter(Role.name == "ssg")
        .order_by(UserModel.last_name)
    )
    
    if include_profiles:
        query = query.options(
            joinedload(UserModel.roles).joinedload(UserRole.role),
            joinedload(UserModel.ssg_profile)
        )
    
    ssg_members = query.offset(skip).limit(limit).all()
    
    return [UserWithRelations.from_orm(user) for user in ssg_members]

# Add these endpoints to your existing router
@router.patch("/{user_id}", response_model=UserWithRelations)
def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: UserModel = Depends(get_current_user_with_roles),
    db: Session = Depends(get_db)
):
    """
    Partially update a user's basic information.
    
    Args:
        user_id: ID of the user to update
        user_update: Updated user data (only fields that need to be changed)
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Updated user with all related data
    """
    # Only admin can update other users, or users can update themselves
    if current_user.id != user_id and not has_required_roles(current_user, ["admin"]):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to update this user"
        )
    
    # Get the user to update
    db_user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Only update fields that are provided in the request
    if user_update.email is not None:
        # Check if email is being changed and if it already exists
        if db_user.email != user_update.email:
            if db.query(UserModel).filter(UserModel.email == user_update.email).first():
                raise HTTPException(status_code=400, detail="Email already registered")
        db_user.email = user_update.email
    
    if user_update.first_name is not None:
        db_user.first_name = user_update.first_name
        
    if user_update.middle_name is not None:
        db_user.middle_name = user_update.middle_name
        
    if user_update.last_name is not None:
        db_user.last_name = user_update.last_name
    
    db.commit()
    db.refresh(db_user)
    
    return UserWithRelations.from_orm(db_user)


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    current_user: UserModel = Depends(get_current_user_with_roles),
    db: Session = Depends(get_db)
):
    """
    Delete a user.
    
    Args:
        user_id: ID of the user to delete
        current_user: Current authenticated user
        db: Database session
    """
    # Only admin can delete users
    if not has_required_roles(current_user, ["admin"]):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Admin role required."
        )
    
    # Get the user to delete
    db_user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Delete the user
    db.delete(db_user)
    db.commit()
    
    return None


@router.patch("/student-profiles/{profile_id}", response_model=UserWithRelations)
def update_student_profile(
    profile_id: int,
    profile_update: StudentProfileBase,
    current_user: UserModel = Depends(get_current_user_with_roles),
    db: Session = Depends(get_db)
):
    """
    Partially update a student profile.
    
    Args:
        profile_id: ID of the student profile to update
        profile_update: Updated profile data (only fields that need to be changed)
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        User with updated student profile
    """
    # Allow admin, SSG, or event-organizer to update student profiles
    required_roles = ["admin", "ssg", "event-organizer"]
    if not has_required_roles(current_user, required_roles):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Requires admin, SSG or event-organizer role"
        )
    
    # Get the profile to update
    profile = db.query(StudentProfile).filter(StudentProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    # Only update fields that are provided in the request
    if profile_update.student_id is not None:
        # Check if student ID is being changed and if it already exists
        if profile.student_id != profile_update.student_id:
            if db.query(StudentProfile).filter(StudentProfile.student_id == profile_update.student_id).first():
                raise HTTPException(status_code=400, detail="Student ID already in use")
        profile.student_id = profile_update.student_id
    
    if profile_update.department_id is not None or profile_update.program_id is not None:
        # If either department or program is being updated, we need to validate both
        department_id = profile_update.department_id if profile_update.department_id is not None else profile.department_id
        program_id = profile_update.program_id if profile_update.program_id is not None else profile.program_id
        
        department = db.get(Department, department_id)
        program = db.get(Program, program_id)
        
        if not department or not program:
            raise HTTPException(status_code=400, detail="Invalid department or program ID")
        
        # Verify program belongs to department (many-to-many check)
        association_exists = db.execute(
            select(program_department_association)
            .where(
                (program_department_association.c.department_id == department.id) &
                (program_department_association.c.program_id == program.id)
            )
        ).first()

        if not association_exists:
            raise HTTPException(
                status_code=400,
                detail=f"Program '{program.name}' is not offered by department '{department.name}'"
            )
        
        if profile_update.department_id is not None:
            profile.department_id = profile_update.department_id
        if profile_update.program_id is not None:
            profile.program_id = profile_update.program_id
    
    if profile_update.year_level is not None:
        profile.year_level = profile_update.year_level
    
    db.commit()
    db.refresh(profile)
    
    # Return the full user with updated profile
    user = db.query(UserModel).filter(UserModel.id == profile.user_id).first()
    return UserWithRelations.from_orm(user)


@router.delete("/student-profiles/{profile_id}", status_code=204)
def delete_student_profile(
    profile_id: int,
    current_user: UserModel = Depends(get_current_user_with_roles),
    db: Session = Depends(get_db)
):
    """
    Delete a student profile.
    
    Args:
        profile_id: ID of the student profile to delete
        current_user: Current authenticated user
        db: Database session
    """
    # Only admin can delete student profiles
    if not has_required_roles(current_user, ["admin"]):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Admin role required."
        )
    
    # Get the profile to delete
    profile = db.query(StudentProfile).filter(StudentProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    # Delete the profile
    db.delete(profile)
    db.commit()
    
    return None


@router.put("/ssg-profiles/{profile_id}", response_model=UserWithRelations)
def update_ssg_profile(
    profile_id: int,
    profile_update: SSGProfileBase,
    current_user: UserModel = Depends(get_current_user_with_roles),
    db: Session = Depends(get_db)
):
    """
    Update an SSG profile.
    
    Args:
        profile_id: ID of the SSG profile to update
        profile_update: Updated profile data
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        User with updated SSG profile
    """
    # Allow admin or SSG to update SSG profiles
    required_roles = ["admin", "ssg"]
    if not has_required_roles(current_user, required_roles):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Requires admin or SSG role"
        )
    
    # Get the profile to update
    profile = db.query(SSGProfile).filter(SSGProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="SSG profile not found")
    
    # Update profile fields (position is validated by Pydantic)
    profile.position = profile_update.position
    
    db.commit()
    db.refresh(profile)
    
    # Return the full user with updated profile
    user = db.query(UserModel).filter(UserModel.id == profile.user_id).first()
    return UserWithRelations.from_orm(user)


@router.delete("/ssg-profiles/{profile_id}", status_code=204)
def delete_ssg_profile(
    profile_id: int,
    current_user: UserModel = Depends(get_current_user_with_roles),
    db: Session = Depends(get_db)
):
    """
    Delete an SSG profile.
    
    Args:
        profile_id: ID of the SSG profile to delete
        current_user: Current authenticated user
        db: Database session
    """
    # Only admin can delete SSG profiles
    if not has_required_roles(current_user, ["admin"]):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Admin role required."
        )
    
    # Get the profile to delete
    profile = db.query(SSGProfile).filter(SSGProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="SSG profile not found")
    
    # Delete the profile
    db.delete(profile)
    db.commit()
    
    return None


@router.put("/{user_id}/roles", response_model=UserWithRelations)
def update_user_roles(
    user_id: int,
    role_update: UserRoleUpdate,
    current_user: UserModel = Depends(get_current_user_with_roles),
    db: Session = Depends(get_db)
):
    """
    Update a user's roles.
    
    Args:
        user_id: ID of the user to update roles for
        roles: List of role names to assign
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        User with updated roles
    """
    # Only admin can update roles
    if not has_required_roles(current_user, ["admin"]):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Admin role required."
        )
    
    # Get the user to update
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Delete existing roles
    db.query(UserRole).filter(UserRole.user_id == user_id).delete()
    
    # Add new roles
    for role_name in role_update.roles:
        role = db.query(Role).filter(Role.name == role_name.value).first()
        if not role:
            raise HTTPException(
                status_code=400,
                detail=f"Role '{role_name.value}' does not exist in database"
            )
        db.add(UserRole(user_id=user.id, role_id=role.id))
    
    db.commit()
    db.refresh(user)
    
    return UserWithRelations.from_orm(user)


@router.get("/{user_id}", response_model=UserWithRelations)
def get_user_by_id(
    user_id: int,
    current_user: UserModel = Depends(get_current_user_with_roles),
    db: Session = Depends(get_db)
):
    """
    Get a user by ID with all profile information.
    
    Args:
        user_id: ID of the user to retrieve
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        User with all related data
    """
    # Allow users to get their own profile or admin/SSG/event-organizer to get any profile
    if current_user.id != user_id and not has_required_roles(current_user, ["admin", "ssg", "event-organizer"]):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to view this user"
        )
    
    # Get the user
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserWithRelations.from_orm(user)


@router.post("/{user_id}/reset-password", status_code=204)
def reset_user_password(
    user_id: int,
    password_update: PasswordUpdate,
    current_user: UserModel = Depends(get_current_user_with_roles),
    db: Session = Depends(get_db)
):
    """
    Reset a user's password.
    
    Args:
        user_id: ID of the user to reset password for
        password: New password
        current_user: Current authenticated user
        db: Database session
    """
    # Only admin can reset passwords, or users can reset their own
    if current_user.id != user_id and not has_required_roles(current_user, ["admin"]):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to reset this user's password"
        )
    
    # Get the user
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update password
    user.set_password(password_update.password)
    db.commit()
    
    return None    

@router.post("/events/{event_id}/ssg-members", response_model=Event)
def assign_ssg_members_to_event(
    event_id: int,
    ssg_member_ids: List[int],
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user_with_roles)
):
    """Assign SSG members to an event"""
    # Check permissions
    required_roles = ["admin", "event-organizer"]
    if not has_required_roles(current_user, required_roles):
        raise HTTPException(403, "Insufficient permissions")

    # Get the event
    event = db.query(Event).get(event_id)
    if not event:
        raise HTTPException(404, "Event not found")

    # Clear existing assignments
    event.ssg_members = []

    # Add new assignments
    for member_id in ssg_member_ids:
        member = db.query(SSGProfile).filter(SSGProfile.user_id == member_id).first()
        if member:
            event.ssg_members.append(member)

    db.commit()
    db.refresh(event)
    return event    