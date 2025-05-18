from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from app.models.user import User as UserModel
from app.models.attendance import Attendance as AttendanceModel
from app.models.user import StudentProfile
from app.schemas.attendance import AttendanceStatus, Attendance, AttendanceWithStudent
from app.models.attendance import Attendance as AttendanceModel
from app.database import get_db
from app.core.security import get_current_user
from app.models.user import User  # Add this import

router = APIRouter(prefix="/attendance", tags=["attendance"])

# Request models
class ManualAttendanceRequest(BaseModel):
    event_id: int
    student_id: str  # Student ID string
    notes: Optional[str] = None

class BulkAttendanceRequest(BaseModel):
    records: List[ManualAttendanceRequest]

class StudentAttendanceFilter(BaseModel):
    event_id: Optional[int] = None
    status: Optional[AttendanceStatus] = None

# 1. Get current student's attendance
@router.get("/students/me", response_model=List[Attendance])
def get_my_attendance(
    event_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current student's attendance records"""
    # Fixed: Better role checking
    user_roles = [role.role.name for role in current_user.roles]
    if "student" not in user_roles or not current_user.student_profile:
        raise HTTPException(403, "User is not a student")
    
    query = db.query(AttendanceModel).filter(
        AttendanceModel.student_id == current_user.student_profile.id
    )
    
    if event_id:
        query = query.filter(AttendanceModel.event_id == event_id)
    
    return query.order_by(AttendanceModel.time_in.desc()).offset(skip).limit(limit).all()

# 2. Face scan attendance - FIXED
@router.post("/face-scan")
def record_face_scan_attendance(
    event_id: int,
    student_id: str,
    current_user: UserModel = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """Record attendance via face scan"""
    # Fixed: Better role checking
    user_roles = [role.role.name for role in current_user.roles]
    if "ssg" not in user_roles:
        raise HTTPException(403, "Requires SSG role")
    
    student = db.query(StudentProfile).filter(
        StudentProfile.student_id == student_id
    ).first()
    
    if not student:
        raise HTTPException(404, f"Student {student_id} not found")
    
    # Check for existing attendance
    existing = db.query(AttendanceModel).filter(
        AttendanceModel.student_id == student.id,
        AttendanceModel.event_id == event_id
    ).first()
    
    if existing:
        # Calculate time difference properly
        time_diff = (datetime.utcnow() - existing.time_in).total_seconds()
        if time_diff < 300:  # 5-minute cooldown
            raise HTTPException(400, f"Duplicate scan detected. Last scan was {int(time_diff/60)} minutes ago.")
    
    # Create attendance record
    attendance = AttendanceModel(
        student_id=student.id,
        event_id=event_id,
        time_in=datetime.utcnow(),
        method="face_scan",
        status=AttendanceStatus.PRESENT,
        verified_by=current_user.id
    )
    
    db.add(attendance)
    db.commit()
    db.refresh(attendance)
    
    return {
        "message": "Attendance recorded successfully",
        "attendance_id": attendance.id,
        "student_id": student_id,
        "time_in": attendance.time_in
    }

# 3. Manual attendance - FIXED
@router.post("/manual")
def record_manual_attendance(
    data: ManualAttendanceRequest = Body(...),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Record manual attendance"""
    # Fixed: Better role checking
    user_roles = [role.role.name for role in current_user.roles]
    if "ssg" not in user_roles:
        raise HTTPException(403, "Requires SSG role")
    
    student = db.query(StudentProfile).filter(
        StudentProfile.student_id == data.student_id
    ).first()
    
    if not student:
        raise HTTPException(404, f"Student {data.student_id} not found")
    
    # Check for existing attendance
    existing = db.query(AttendanceModel).filter(
        AttendanceModel.student_id == student.id,
        AttendanceModel.event_id == data.event_id
    ).first()
    
    if existing:
        raise HTTPException(400, f"Attendance already exists for student {data.student_id}")
    
    # Create attendance record
    attendance = AttendanceModel(
        student_id=student.id,
        event_id=data.event_id,
        time_in=datetime.utcnow(),
        method="manual",
        status="present",  # Use direct string
        verified_by=current_user.id,
        notes=data.notes
    )
    
    db.add(attendance)
    db.commit()
    db.refresh(attendance)
    
    return {
        "message": f"Recorded attendance for {data.student_id}",
        "attendance_id": attendance.id
    }

# 4. Bulk attendance
@router.post("/bulk")
def record_bulk_attendance(
    data: BulkAttendanceRequest,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Record multiple attendances at once"""
    if not any(role.role.name == "ssg" for role in current_user.roles):
        raise HTTPException(403, "Requires SSG role")
    
    results = []
    for record in data.records:
        student = db.query(StudentProfile).filter(
            StudentProfile.student_id == record.student_id
        ).first()
        
        if not student:
            results.append({"student_id": record.student_id, "status": "not_found"})
            continue
            
        existing = db.query(AttendanceModel).filter(
            AttendanceModel.student_id == student.id,
            AttendanceModel.event_id == record.event_id
        ).first()
        
        if existing:
            results.append({"student_id": record.student_id, "status": "exists"})
            continue
            
        attendance = AttendanceModel(
            student_id=student.id,
            event_id=record.event_id,
            time_in=datetime.utcnow(),
            method="manual",
            status=AttendanceStatus.PRESENT,
            verified_by=current_user.id,
            notes=record.notes
        )
        db.add(attendance)
        results.append({"student_id": record.student_id, "status": "recorded"})
    
    db.commit()
    return {"processed": len(results), "results": results}

# 5. Mark excused
@router.post("/events/{event_id}/mark-excused")
def mark_excused_attendance(
    event_id: int,
    student_ids: List[str],
    reason: str,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark students as excused for an event"""
    if not any(role.role.name in ["ssg", "admin"] for role in current_user.roles):
        raise HTTPException(403, "Requires SSG/Admin role")
    
    students = db.query(StudentProfile).filter(
        StudentProfile.student_id.in_(student_ids)
    ).all()
    
    for student in students:
        attendance = db.query(AttendanceModel).filter(
            AttendanceModel.student_id == student.id,
            AttendanceModel.event_id == event_id
        ).first()
        
        if attendance:
            attendance.status = AttendanceStatus.EXCUSED
            attendance.notes = reason
        else:
            attendance = AttendanceModel(
                student_id=student.id,
                event_id=event_id,
                status=AttendanceStatus.EXCUSED,
                notes=reason,
                method="manual",
                verified_by=current_user.id
            )
            db.add(attendance)
    
    db.commit()
    return {"message": f"Marked {len(students)} students as excused"}

# 6. Get event attendees
@router.get("/events/{event_id}/attendees", response_model=List[Attendance])
def get_event_attendees(
    event_id: int,
    status: Optional[AttendanceStatus] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get attendees for an event"""
    if not any(role.role.name in ["ssg", "admin"] for role in current_user.roles):
        raise HTTPException(403, "Requires SSG/Admin role")
    
    query = db.query(AttendanceModel).filter(
        AttendanceModel.event_id == event_id
    )
    
    if status:
        query = query.filter(AttendanceModel.status == status)
    
    return query.order_by(
        AttendanceModel.status,
        AttendanceModel.time_in
    ).offset(skip).limit(limit).all()

# 7. Attendance summary
@router.get("/events/{event_id}/summary")
def get_attendance_summary(
    event_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get attendance statistics for an event"""
    if not any(role.role.name in ["ssg", "admin"] for role in current_user.roles):
        raise HTTPException(403, "Requires SSG/Admin role")
    
    total = db.query(func.count(AttendanceModel.id)).filter(
        AttendanceModel.event_id == event_id
    ).scalar()
    
    counts = db.query(
        AttendanceModel.status,
        func.count(AttendanceModel.id)
    ).filter(
        AttendanceModel.event_id == event_id
    ).group_by(
        AttendanceModel.status
    ).all()
    
    return {
        "total": total,
        "statuses": {
            status: {
                "count": count,
                "percentage": round((count / total) * 100, 2) if total else 0
            } for status, count in counts
        }
    }


# 4. Time-out recording - FIXED
@router.post("/{attendance_id}/time-out")
def record_time_out(
    attendance_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Record time-out for an attendance record"""
    # Check if user has permission
    user_roles = [role.role.name for role in current_user.roles]
    if not any(role in ["ssg", "admin"] for role in user_roles):
        raise HTTPException(403, "Requires SSG or Admin role")
    
    attendance = db.query(AttendanceModel).filter(
        AttendanceModel.id == attendance_id
    ).first()
    
    if not attendance:
        raise HTTPException(404, "Attendance record not found")
    
    if attendance.time_out:
        raise HTTPException(400, "Time-out already recorded")
    
    # Record time-out
    attendance.time_out = datetime.utcnow()
    db.commit()
    
    # Calculate duration
    duration_seconds = (attendance.time_out - attendance.time_in).total_seconds()
    duration_minutes = int(duration_seconds / 60)
    
    return {
        "message": "Time-out recorded successfully",
        "attendance_id": attendance_id,
        "time_in": attendance.time_in,
        "time_out": attendance.time_out,
        "duration_minutes": duration_minutes
    }

@router.post("/face-scan-timeout")
def record_face_scan_timeout(
    event_id: int,
    student_id: str,
    current_user: UserModel = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """Record timeout via face scan"""
    # Check permissions
    user_roles = [role.role.name for role in current_user.roles]
    if "ssg" not in user_roles:
        raise HTTPException(403, "Requires SSG role")
    
    # Find student
    student = db.query(StudentProfile).filter(
        StudentProfile.student_id == student_id
    ).first()
    
    if not student:
        raise HTTPException(404, f"Student {student_id} not found")
    
    # Find existing attendance record
    attendance = db.query(AttendanceModel).filter(
        AttendanceModel.student_id == student.id,
        AttendanceModel.event_id == event_id,
        AttendanceModel.time_out.is_(None)  # Only get records without timeout
    ).first()
    
    if not attendance:
        raise HTTPException(404, f"No active attendance found for student {student_id}")
    
    # Check if timeout already recorded
    if attendance.time_out:
        raise HTTPException(400, f"Timeout already recorded for this attendance")
    
    # Record timeout
    attendance.time_out = datetime.utcnow()
    db.commit()
    
    # Calculate duration
    duration_seconds = (attendance.time_out - attendance.time_in).total_seconds()
    duration_minutes = int(duration_seconds / 60)
    
    return {
        "message": "Face scan timeout recorded successfully",
        "attendance_id": attendance.id,
        "student_id": student_id,
        "time_in": attendance.time_in,
        "time_out": attendance.time_out,
        "duration_minutes": duration_minutes
    }    

@router.get("/events/{event_id}/attendances", response_model=List[Attendance])
def get_attendances_by_event(
    event_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all attendance records for a specific event"""
    return db.query(AttendanceModel)\
            .filter(AttendanceModel.event_id == event_id)\
            .order_by(AttendanceModel.time_in.desc())\
            .offset(skip)\
            .limit(limit)\
            .all()

@router.get("/events/{event_id}/attendances/{status}", response_model=List[Attendance])
def get_attendances_by_event_and_status(
    event_id: int,
    status: AttendanceStatus,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get attendance records for an event filtered by status"""
    return db.query(AttendanceModel)\
            .filter(
                AttendanceModel.event_id == event_id,
                AttendanceModel.status == status
            )\
            .order_by(AttendanceModel.time_in.desc())\
            .offset(skip)\
            .limit(limit)\
            .all()

@router.get("/events/{event_id}/attendances-with-students", response_model=List[AttendanceWithStudent])
def get_attendances_with_students(
    event_id: int,
    db: Session = Depends(get_db)
):
    """Get attendance records with student information"""
    results = db.query(
        AttendanceModel,
        StudentProfile.student_id,
        User.first_name,
        User.last_name
    )\
    .join(StudentProfile, AttendanceModel.student_id == StudentProfile.id)\
    .join(User, StudentProfile.user_id == User.id)\
    .filter(AttendanceModel.event_id == event_id)\
    .all()

    return [AttendanceWithStudent(
        attendance=attendance,
        student_id=student_id,
        student_name=f"{first_name} {last_name}"
    ) for attendance, student_id, first_name, last_name in results]