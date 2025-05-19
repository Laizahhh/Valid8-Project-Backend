from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from datetime import datetime, timezone
from typing import List, Optional, Dict
from pydantic import BaseModel

from app.models.user import User as UserModel
from app.models.attendance import Attendance as AttendanceModel
from app.models.user import StudentProfile
from app.schemas.attendance import AttendanceStatus, Attendance, AttendanceWithStudent, StudentAttendanceRecord, StudentAttendanceResponse, AttendanceReportResponse
from app.models.attendance import Attendance as AttendanceModel
from app.database import get_db
from app.core.security import get_current_user
from app.models.user import User  # Add this import
from app.models.event import Event  # This imports your Event model
from app.models.program import Program  # This imports your Event model
from app.models.associations import event_program_association  # This imports your Event model


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
        time_in=datetime.now(timezone.utc),
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
        "attendance_id": attendance.id}

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
    attendance.time_out = datetime.now(timezone.utc)
    db.commit()
    
    # Calculate duration
    duration_seconds = (attendance.time_out - attendance.time_in).total_seconds()
    duration_minutes = int(duration_seconds / 60)
    
    return {
        "message": "Time-out recorded successfully",
        "attendance_id": attendance_id,
        "time_in": attendance.time_in,
        "time_out": attendance.time_out,
        "duration_minutes": duration_minutes}

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

@router.get("/events/{event_id}/attendances", response_model=List[AttendanceWithStudent])
def get_attendances_by_event(
    event_id: int,
    active_only: bool = Query(True, description="Only show active attendances (no time_out)"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all attendance records for a specific event with student details"""
    query = db.query(
        AttendanceModel,
        StudentProfile.student_id,
        User.first_name,
        User.last_name
    )\
    .join(StudentProfile, AttendanceModel.student_id == StudentProfile.id)\
    .join(User, StudentProfile.user_id == User.id)\
    .filter(AttendanceModel.event_id == event_id)
    
    if active_only:
        query = query.filter(AttendanceModel.time_out.is_(None))
    
    results = query.order_by(AttendanceModel.time_in.desc())\
                  .offset(skip)\
                  .limit(limit)\
                  .all()

    return [AttendanceWithStudent(
        attendance=attendance,
        student_id=student_id,
        student_name=f"{first_name} {last_name}"
    ) for attendance, student_id, first_name, last_name in results]

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

@router.get("/students/records", response_model=List[StudentAttendanceResponse])
def get_all_student_attendance_records(
    student_ids: List[str] = Query(None, description="Filter by specific student IDs"),
    event_id: Optional[int] = Query(None, description="Filter by event ID"),
    status: Optional[AttendanceStatus] = Query(None, description="Filter by status"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Get comprehensive attendance records for students with filtering options
    Requires admin or ssg role
    """
    # Check permissions
    if not any(role.role.name in ["admin", "ssg"] for role in current_user.roles):
        raise HTTPException(status_code=403, detail="Requires admin or SSG role")

    # Base query joining all necessary tables
    query = db.query(
        AttendanceModel,
        StudentProfile.student_id,
        User.first_name,
        User.last_name,
        Event.name.label('event_name')
    ).join(
        StudentProfile, AttendanceModel.student_id == StudentProfile.id
    ).join(
        User, StudentProfile.user_id == User.id
    ).join(
        Event, AttendanceModel.event_id == Event.id
    )

    # Apply filters
    if student_ids:
        query = query.filter(StudentProfile.student_id.in_(student_ids))
    if event_id:
        query = query.filter(AttendanceModel.event_id == event_id)
    if status:
        query = query.filter(AttendanceModel.status == status)

    # Execute query
    results = query.order_by(
        StudentProfile.student_id,
        AttendanceModel.time_in.desc()
    ).offset(skip).limit(limit).all()

    # Group results by student
    student_records = {}
    for attendance, student_id, first_name, last_name, event_name in results:
        # Calculate duration if time_out exists
        duration = None
        if attendance.time_out:
            duration = int((attendance.time_out - attendance.time_in).total_seconds() / 60)

        record = StudentAttendanceRecord(
            id=attendance.id,
            event_id=attendance.event_id,
            event_name=event_name,
            time_in=attendance.time_in,
            time_out=attendance.time_out,
            status=attendance.status,
            method=attendance.method,
            notes=attendance.notes,
            duration_minutes=duration
        )

        if student_id not in student_records:
            student_records[student_id] = {
                'student_id': student_id,
                'student_name': f"{first_name} {last_name}",
                'attendances': []
            }
        student_records[student_id]['attendances'].append(record)

    # Convert to response format
    response = []
    for student_id, data in student_records.items():
        response.append(StudentAttendanceResponse(
            student_id=student_id,
            student_name=data['student_name'],
            total_records=len(data['attendances']),
            attendances=data['attendances']
        ))

    return response

@router.get("/students/{student_id}/records", response_model=StudentAttendanceResponse)
def get_student_attendance_records(
    student_id: str,
    event_id: Optional[int] = Query(None),
    status: Optional[AttendanceStatus] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Get all attendance records for a specific student"""
    # Permission check - allow students to view their own records
    user_roles = [role.role.name for role in current_user.roles]
    if "student" in user_roles and current_user.student_profile.student_id != student_id:
        raise HTTPException(403, "Can only view your own records")

    student = db.query(StudentProfile).filter(
        StudentProfile.student_id == student_id
    ).first()

    if not student:
        raise HTTPException(404, "Student not found")

    # Query attendances with event names
    query = db.query(
        AttendanceModel,
        Event.name.label('event_name')
    ).join(
        Event, AttendanceModel.event_id == Event.id
    ).filter(
        AttendanceModel.student_id == student.id
    )

    if event_id:
        query = query.filter(AttendanceModel.event_id == event_id)
    if status:
        query = query.filter(AttendanceModel.status == status)

    results = query.order_by(
        AttendanceModel.time_in.desc()
    ).offset(skip).limit(limit).all()

    # Process results
    attendances = []
    for attendance, event_name in results:
        duration = None
        if attendance.time_out:
            duration = int((attendance.time_out - attendance.time_in).total_seconds() / 60)

        attendances.append(StudentAttendanceRecord(
            id=attendance.id,
            event_id=attendance.event_id,
            event_name=event_name,
            time_in=attendance.time_in,
            time_out=attendance.time_out,
            status=attendance.status,
            method=attendance.method,
            notes=attendance.notes,
            duration_minutes=duration
        ))

    return StudentAttendanceResponse(
        student_id=student_id,
        student_name=f"{student.user.first_name} {student.user.last_name}",
        total_records=len(attendances),
        attendances=attendances
    )  

@router.get("/me/records", response_model=List[StudentAttendanceResponse])
def get_my_attendance_records(
    current_user: UserModel = Depends(get_current_user),
    event_id: Optional[int] = Query(None),
    status: Optional[AttendanceStatus] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get attendance records for the currently authenticated student
    """
    # Verify the user is a student
    if not current_user.student_profile:
        raise HTTPException(
            status_code=403,
            detail="Only students can access their own attendance records"
        )

    student = current_user.student_profile

    # Query attendances with event names
    query = db.query(
        AttendanceModel,
        Event.name.label('event_name')
    ).join(
        Event, AttendanceModel.event_id == Event.id
    ).filter(
        AttendanceModel.student_id == student.id
    )

    if event_id:
        query = query.filter(AttendanceModel.event_id == event_id)
    if status:
        query = query.filter(AttendanceModel.status == status)

    results = query.order_by(
        AttendanceModel.time_in.desc()
    ).offset(skip).limit(limit).all()

    # Process results
    attendances = []
    for attendance, event_name in results:
        duration = None
        if attendance.time_out:
            duration = int((attendance.time_out - attendance.time_in).total_seconds() / 60)

        attendances.append(StudentAttendanceRecord(
            id=attendance.id,
            event_id=attendance.event_id,
            event_name=event_name,
            time_in=attendance.time_in,
            time_out=attendance.time_out,
            status=attendance.status,
            method=attendance.method,
            notes=attendance.notes,
            duration_minutes=duration
        ))

    return [StudentAttendanceResponse(
        student_id=student.student_id,
        student_name=f"{current_user.first_name} {current_user.last_name}",
        total_records=len(attendances),
        attendances=attendances
    )]      



@router.get("/events/{event_id}/report", response_model=AttendanceReportResponse)
def get_event_attendance_report(
    event_id: int,
    program_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Generate an attendance report for a specific event with optional program filter
    Returns data in format:
    {
        "event_name": "Annual Science Fair",
        "event_date": "April 10, 2025",
        "event_location": "Main Auditorium",
        "total_participants": 21,
        "attendees": 13,
        "absentees": 8,
        "attendance_rate": 62.0,
        "programs": [{"id": 1, "name": "Computer Science"}, ...],
        "program_breakdown": [
            {"program": "Computer Science", "total": 10, "present": 7, "absent": 3},
            ...
        ]
    }
    """
    # Get basic event info
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Get all programs associated with this event for the filter dropdown
    programs = db.query(Program).join(
        event_program_association,
        Program.id == event_program_association.c.program_id
    ).filter(
        event_program_association.c.event_id == event_id
    ).all()

    # Base query for attendance counts
    query = db.query(
        AttendanceModel.status,
        func.count(AttendanceModel.id).label("count")
    ).filter(
        AttendanceModel.event_id == event_id
    )

    # Apply program filter if specified
    if program_id:
        query = query.join(
            StudentProfile,
            AttendanceModel.student_id == StudentProfile.id
        ).filter(
            StudentProfile.program_id == program_id
        )

    # Get attendance counts by status
    attendance_counts = query.group_by(AttendanceModel.status).all()

    # Calculate totals
    counts = {status: count for status, count in attendance_counts}
    total_participants = sum(counts.values())
    attendees = counts.get("present", 0)
    absentees = counts.get("absent", 0) + counts.get("excused", 0)
    attendance_rate = (attendees / total_participants * 100) if total_participants > 0 else 0

    # Get breakdown by program
    program_breakdown = db.query(
        Program.name.label("program"),
        func.count(AttendanceModel.id).label("total"),
        func.sum(case((AttendanceModel.status == "present", 1), else_=0)).label("present"),
        func.sum(case((AttendanceModel.status.in_(["absent", "excused"]), 1), else_=0)).label("absent")
    ).join(
        StudentProfile,
        AttendanceModel.student_id == StudentProfile.id
    ).join(
        Program,
        StudentProfile.program_id == Program.id
    ).filter(
        AttendanceModel.event_id == event_id
    ).group_by(
        Program.name
    ).all()

    return {
        "event_name": event.name,
        "event_date": event.start_datetime.strftime("%B %d, %Y"),
        "event_location": event.location,
        "total_participants": total_participants,
        "attendees": attendees,
        "absentees": absentees,
        "attendance_rate": round(attendance_rate, 1),
        "programs": [{"id": p.id, "name": p.name} for p in programs],
        "program_breakdown": [
            {
                "program": item.program,
                "total": item.total,
                "present": item.present,
                "absent": item.absent
            } for item in program_breakdown
        ]
    }
@router.get("/events/{event_id}/report", response_model=AttendanceReportResponse)
def get_event_attendance_report(
    event_id: int,
    program_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Generate an attendance report for a specific event with optional program filter
    Returns data in format:
    {
        "event_name": "Annual Science Fair",
        "event_date": "April 10, 2025",
        "event_location": "Main Auditorium",
        "total_participants": 21,
        "attendees": 13,
        "absentees": 8,
        "attendance_rate": 62.0,
        "programs": [{"id": 1, "name": "Computer Science"}, ...],
        "program_breakdown": [
            {"program": "Computer Science", "total": 10, "present": 7, "absent": 3},
            ...
        ]
    }
    """
    # Get basic event info
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Get all programs associated with this event for the filter dropdown
    programs = db.query(Program).join(
        event_program_association,
        Program.id == event_program_association.c.program_id
    ).filter(
        event_program_association.c.event_id == event_id
    ).all()

    # Base query for attendance counts
    query = db.query(
        AttendanceModel.status,
        func.count(AttendanceModel.id).label("count")
    ).filter(
        AttendanceModel.event_id == event_id
    )

    # Apply program filter if specified
    if program_id:
        query = query.join(
            StudentProfile,
            AttendanceModel.student_id == StudentProfile.id
        ).filter(
            StudentProfile.program_id == program_id
        )

    # Get attendance counts by status
    attendance_counts = query.group_by(AttendanceModel.status).all()

    # Calculate totals
    counts = {status: count for status, count in attendance_counts}
    total_participants = sum(counts.values())
    attendees = counts.get("present", 0)
    absentees = counts.get("absent", 0) + counts.get("excused", 0)
    attendance_rate = (attendees / total_participants * 100) if total_participants > 0 else 0

    # Get breakdown by program
    program_breakdown = db.query(
        Program.name.label("program"),
        func.count(AttendanceModel.id).label("total"),
        func.sum(case((AttendanceModel.status == "present", 1), else_=0)).label("present"),
        func.sum(case((AttendanceModel.status.in_(["absent", "excused"]), 1), else_=0)).label("absent")
    ).join(
        StudentProfile,
        AttendanceModel.student_id == StudentProfile.id
    ).join(
        Program,
        StudentProfile.program_id == Program.id
    ).filter(
        AttendanceModel.event_id == event_id
    ).group_by(
        Program.name
    ).all()

    return {
        "event_name": event.name,
        "event_date": event.start_datetime.strftime("%B %d, %Y"),
        "event_location": event.location,
        "total_participants": total_participants,
        "attendees": attendees,
        "absentees": absentees,
        "attendance_rate": round(attendance_rate, 1),
        "programs": [{"id": p.id, "name": p.name} for p in programs],
        "program_breakdown": [
            {
                "program": item.program,
                "total": item.total,
                "present": item.present,
                "absent": item.absent
            } for item in program_breakdown
        ]
    }    