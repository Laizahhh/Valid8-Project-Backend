from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session,joinedload
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import logging

from app.schemas.event import (
    Event as EventSchema,
    EventCreate,
    EventUpdate,
    EventWithRelations,
    EventStatus
)
from app.models.event import Event as EventModel, EventStatus as ModelEventStatus
from app.models.department import Department as DepartmentModel
from app.models.program import Program as ProgramModel
from app.models.user import SSGProfile
from app.database import get_db
from app.core.security import get_current_user
# Add these imports at the top of your event router (app/api/endpoints/event.py)
from typing import Optional  # For Optional type hint
from app.models.user import User as UserModel  # For UserModel
from app.models.attendance import Attendance as AttendanceModel  # For AttendanceModel
from sqlalchemy import func  # For aggregate functions


router = APIRouter(prefix="/events", tags=["events"])
logger = logging.getLogger(__name__)

# 1. Create Event
@router.post("/", response_model=EventWithRelations, status_code=status.HTTP_201_CREATED)
def create_event(
    event: EventCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Create a new event"""
    try:
        # Validate permissions
        if not any(role.role.name in ["ssg", "admin", "event-organizer"] for role in current_user.roles):
            raise HTTPException(status_code=403, detail="Not authorized to create events")
        
        # Validate datetime
        if event.start_datetime >= event.end_datetime:
            raise HTTPException(status_code=400, detail="End datetime must be after start datetime")
        
        # Create event
        db_event = EventModel(
            name=event.name,
            location=event.location,
            start_datetime=event.start_datetime,
            end_datetime=event.end_datetime,
            status=ModelEventStatus[event.status.value.upper()]
        )
        db.add(db_event)
        db.flush()  # Get ID before adding relationships
        
        # Add relationships
        if event.department_ids:
            departments = db.query(DepartmentModel).filter(
                DepartmentModel.id.in_(event.department_ids)
            ).all()
            if len(departments) != len(event.department_ids):
                missing = set(event.department_ids) - {d.id for d in departments}
                raise HTTPException(404, f"Departments not found: {missing}")
            db_event.departments = departments
        
        if event.program_ids:
            programs = db.query(ProgramModel).options(
            joinedload(ProgramModel.departments)  # Add this
        ).filter(
            ProgramModel.id.in_(event.program_ids)
        ).all()
            if len(programs) != len(event.program_ids):
                missing = set(event.program_ids) - {p.id for p in programs}
                raise HTTPException(404, f"Programs not found: {missing}")
            db_event.programs = programs
        
            if event.ssg_member_ids:
                ssg_profiles = db.query(SSGProfile).options(
                joinedload(SSGProfile.user)  # ← ADD THIS
    )           .filter(
                SSGProfile.user_id.in_(event.ssg_member_ids)
                ).all()
    
                if len(ssg_profiles) != len(event.ssg_member_ids):
                    missing = set(event.ssg_member_ids) - {s.user_id for s in ssg_profiles}
                    raise HTTPException(404, f"SSG members not found: {missing}")
    
                db_event.ssg_members = ssg_profiles
        
        db.commit()
        db.refresh(db_event)  # This should load departments/programs/ssg_members thanks to lazy="joined"
         # Debug: Verify loaded relationships
        print(f"Departments: {[d.id for d in db_event.departments]}")
        return db_event
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "Event creation failed (possible duplicate)")
    except Exception as e:
        db.rollback()
        logger.error(f"Event creation error: {str(e)}")
        raise HTTPException(500, "Internal server error")

# 2. Get All Events
@router.get("/", response_model=list[EventSchema])
def read_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[EventStatus] = None,
    start_from: Optional[datetime] = None,
    end_at: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    """Get paginated list of events with optional filters"""
    query = db.query(EventModel).options(
        joinedload(EventModel.ssg_members).joinedload(SSGProfile.user)  # ← ADD THIS
    )
    if status:
        query = query.filter(EventModel.status == ModelEventStatus[status.value.upper()])
    if start_from:
        query = query.filter(EventModel.start_datetime >= start_from)
    if end_at:
        query = query.filter(EventModel.end_datetime <= end_at)
    
    events = query.order_by(EventModel.start_datetime).offset(skip).limit(limit).all()
    return events

# Add this endpoint to your router
@router.get("/ongoing", response_model=list[EventSchema])
def get_ongoing_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Get all ongoing events"""
    events = db.query(EventModel).options(
        joinedload(EventModel.departments),
        joinedload(EventModel.programs),
        joinedload(EventModel.ssg_members).joinedload(SSGProfile.user)
    ).filter(
        EventModel.status == ModelEventStatus.ONGOING
    ).order_by(EventModel.start_datetime).offset(skip).limit(limit).all()
    
    return events

# 3. Get Single Event
@router.get("/{event_id}", response_model=EventWithRelations)
def read_event(
    event_id: int,
    db: Session = Depends(get_db)
):
    """Get complete event details with all relationships"""
    event = db.query(EventModel).options(
        joinedload(EventModel.programs).joinedload(ProgramModel.departments),
        joinedload(EventModel.departments),
        joinedload(EventModel.ssg_members).joinedload(SSGProfile.user)  # ← ADD THIS
    ).filter(EventModel.id == event_id).first()
    
    if not event:
        raise HTTPException(404, "Event not found")
    
    return event

# 4. Update Event
@router.patch("/{event_id}", response_model=EventSchema)
def update_event(
    event_id: int,
    event_update: EventUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Update event details"""
    try:
        # Validate permissions - only allow authorized roles to update
        if not any(role.role.name in ["ssg", "admin", "event-organizer"] for role in current_user.roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update events"
            )
        
        # Get the existing event
        db_event = db.query(EventModel).filter(EventModel.id == event_id).first()
        if not db_event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found"
            )

        # Prepare the new datetime values
        new_start = event_update.start_datetime if event_update.start_datetime is not None else db_event.start_datetime
        new_end = event_update.end_datetime if event_update.end_datetime is not None else db_event.end_datetime

        # Validate datetime
        if new_start >= new_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End datetime must be after start datetime"
            )

        # Update basic fields
        if event_update.name is not None:
            db_event.name = event_update.name
        if event_update.location is not None:
            db_event.location = event_update.location
        db_event.start_datetime = new_start
        db_event.end_datetime = new_end
        if event_update.status is not None:
            db_event.status = ModelEventStatus[event_update.status.value.upper()]

        # Update relationships if provided
        if event_update.department_ids is not None:
            db_event.departments = []
            db.flush()
            departments = db.query(DepartmentModel).filter(
                DepartmentModel.id.in_(event_update.department_ids)
            ).all()
            if len(departments) != len(event_update.department_ids):
                missing = set(event_update.department_ids) - {d.id for d in departments}
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Departments not found: {missing}"
                )
            db_event.departments = departments
        
        if event_update.program_ids is not None:
            db_event.programs = []
            db.flush()
            programs = db.query(ProgramModel).options(
            joinedload(ProgramModel.departments)
            ).filter(
            ProgramModel.id.in_(event_update.program_ids)
            ).all()
    
            if len(programs) != len(event_update.program_ids):
                missing = set(event_update.program_ids) - {p.id for p in programs}
                raise HTTPException(404, f"Programs not found: {missing}")
    
            db_event.programs = programs
        if event_update.ssg_member_ids is not None:
            db_event.ssg_members = []
            db.flush()
            ssg_profiles = db.query(SSGProfile).options(
            joinedload(SSGProfile.user)  # ← ADD THIS
            ).filter(
            SSGProfile.user_id.in_(event_update.ssg_member_ids)
            ).all()
    
            if len(ssg_profiles) != len(event_update.ssg_member_ids):
                missing = set(event_update.ssg_member_ids) - {s.user_id for s in ssg_profiles}
                raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,detail=f"SSG members not found: {missing}")
            db_event.ssg_members = ssg_profiles
        
        db.commit()
        db.refresh(db_event)
        return db_event
        
    except HTTPException as he:
        db.rollback()
        raise he
    except IntegrityError as ie:
        db.rollback()
        logger.error(f"Integrity error during event update: {str(ie)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Update failed due to data integrity issues"
        )
    except ValueError as ve:
        db.rollback()
        logger.error(f"Value error during event update: {str(ve)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid data format: {str(ve)}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during event update: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# 5. Delete Event
@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)  # Require authentication
):
    # 1. Check if user has admin or event-organizer role
    user_roles = {role.role.name for role in current_user.roles}
    if not ({"admin", "event-organizer"} & user_roles):
        raise HTTPException(403, "Admin or event-organizer access required")

    # 2. Find the event
    event = db.query(EventModel).options(
        joinedload(EventModel.attendances),
        joinedload(EventModel.departments),
        joinedload(EventModel.programs),
        joinedload(EventModel.ssg_members)
    ).filter(EventModel.id == event_id).first()

    if not event:
        raise HTTPException(404, "Event not found")

    # 3. Clear relationships (prevent foreign key errors)
    event.departments = []
    event.programs = []
    event.ssg_members = []

    # 4. Delete attendances (if cascade isn't working)
    for attendance in event.attendances:
        db.delete(attendance)

    # 5. Delete the event
    db.delete(event)
    db.commit()


# 6. Get Event Attendees
@router.get("/{event_id}/attendees")
def get_event_attendees(
    event_id: int,
    status: Optional[EventStatus] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get attendees for a specific event"""
    event = db.query(EventModel).filter(EventModel.id == event_id).first()
    if not event:
        raise HTTPException(404, "Event not found")
    
    query = db.query(AttendanceModel).filter(
        AttendanceModel.event_id == event_id
    )
    
    if status:
        query = query.filter(AttendanceModel.status == status)
    
    return query.order_by(
        AttendanceModel.status,
        AttendanceModel.time_in
    ).offset(skip).limit(limit).all()

# 7. Get Event Statistics
@router.get("/{event_id}/stats")
def get_event_stats(
    event_id: int,
    db: Session = Depends(get_db)
):
    """Get attendance statistics for an event"""
    event = db.query(EventModel).filter(EventModel.id == event_id).first()
    if not event:
        raise HTTPException(404, "Event not found")
    
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

# New endpoint to handle status updates only - add this to your router

@router.patch("/{event_id}/status", response_model=EventSchema)
def update_event_status(
    event_id: int,
    status: EventStatus,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Update event status only"""
    try:
        # Validate permissions
        if not any(role.role.name in ["ssg", "admin", "event-organizer"] for role in current_user.roles):
            raise HTTPException(403, "Not authorized to update event status")
        
        # Get the existing event
        db_event = db.query(EventModel).filter(EventModel.id == event_id).first()
        if not db_event:
            raise HTTPException(404, "Event not found")
        
        # Update only the status
        db_event.status = ModelEventStatus[status.value.upper()]
        
        db.commit()
        db.refresh(db_event)
        return db_event
        
    except Exception as e:
        db.rollback()
        logger.error(f"Status update error: {str(e)}")
        raise HTTPException(500, f"Internal server error: {str(e)}")    