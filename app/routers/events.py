from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.schemas.event import Event as EventSchema, EventCreate, EventWithRelations, EventStatus
from app.models.event import Event as EventModel, EventStatus as ModelEventStatus
from app.models.department import Department as DepartmentModel
from app.models.program import Program as ProgramModel
from app.models.user import SSGProfile
from app.database import get_db
from datetime import datetime
import logging

router = APIRouter(prefix="/events", tags=["events"])
logger = logging.getLogger(__name__)

@router.post("/", response_model=EventSchema, status_code=status.HTTP_201_CREATED)
def create_event(event: EventCreate, db: Session = Depends(get_db)):
    try:
        logger.info(f"Creating event: {event.name}")
        
        # Validate start/end times
        if event.start_datetime >= event.end_datetime:
            raise HTTPException(status_code=400, detail="End datetime must be after start datetime")
        
        # Create event instance
        db_event = EventModel(
            name=event.name,
            location=event.location,
            start_datetime=event.start_datetime,
            end_datetime=event.end_datetime,
            status=ModelEventStatus[event.status.value.upper()]  # Convert schema enum to model enum
        )
        
        # Add to session to get ID
        db.add(db_event)
        db.flush()
        
        # Add SSG member relationships
        if event.ssg_member_ids:
            ssg_members = db.query(SSGProfile).filter(
                SSGProfile.id.in_(event.ssg_member_ids)
            ).all()
            
            if len(ssg_members) != len(event.ssg_member_ids):
                found_ids = {s.id for s in ssg_members}
                missing_ids = set(event.ssg_member_ids) - found_ids
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"SSG members not found: {missing_ids}"
                )
                
            db_event.ssg_members = ssg_members
        # Add department relationships
        if event.department_ids:
            departments = db.query(DepartmentModel).filter(
                DepartmentModel.id.in_(event.department_ids)
            ).all()
            
            if len(departments) != len(event.department_ids):
                found_ids = {d.id for d in departments}
                missing_ids = set(event.department_ids) - found_ids
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Departments not found: {missing_ids}"
                )
                
            db_event.departments = departments
        
        # Add program relationships
        if event.program_ids:
            programs = db.query(ProgramModel).filter(
                ProgramModel.id.in_(event.program_ids)
            ).all()
            
            if len(programs) != len(event.program_ids):
                found_ids = {p.id for p in programs}
                missing_ids = set(event.program_ids) - found_ids
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Programs not found: {missing_ids}"
                )
                
            db_event.programs = programs
        
        db.commit()
        db.refresh(db_event)
        
        return EventSchema(
            id=db_event.id,
            name=db_event.name,
            location=db_event.location,
            start_datetime=db_event.start_datetime,
            end_datetime=db_event.end_datetime,
            status=EventStatus(db_event.status.value),
            department_ids=[d.id for d in db_event.departments],
            program_ids=[p.id for p in db_event.programs]
        )
        
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Event creation failed")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=list[EventSchema])
def read_events(
    skip: int = 0,
    limit: int = 100,
    status: EventStatus = None,
    start_from: datetime = None,
    end_at: datetime = None,
    db: Session = Depends(get_db)
):
    query = db.query(EventModel)
    
    if status:
        query = query.filter(EventModel.status == ModelEventStatus[status.value.upper()])
    if start_from:
        query = query.filter(EventModel.start_datetime >= start_from)
    if end_at:
        query = query.filter(EventModel.end_datetime <= end_at)
    
    events = query.offset(skip).limit(limit).all()
    
    return [
        EventSchema(
            id=event.id,
            name=event.name,
            location=event.location,
            start_datetime=event.start_datetime,
            end_datetime=event.end_datetime,
            status=EventStatus(event.status.value),
            department_ids=[d.id for d in event.departments],
            program_ids=[p.id for p in event.programs]
        )
        for event in events
    ]

# ... keep your existing read_event endpoint ...

@router.get("/{event_id}", response_model=EventWithRelations)
def read_event(event_id: int, db: Session = Depends(get_db)):
    db_event = db.query(EventModel).filter(EventModel.id == event_id).first()
    if db_event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Log actual relationships from database
    logger.info(f"Retrieved event: ID={db_event.id}, Name={db_event.name}")
    logger.info(f"Associated departments: {[d.id for d in db_event.departments]}")
    logger.info(f"Associated programs: {[p.id for p in db_event.programs]}")
    
    # Create response with explicitly loaded relationships
    return EventWithRelations(
        id=db_event.id,
        name=db_event.name,
        location=db_event.location,
        start_datetime=db_event.start_datetime,
        end_datetime=db_event.end_datetime,
        department_ids=[d.id for d in db_event.departments],
        program_ids=[p.id for p in db_event.programs],
        departments=db_event.departments,
        programs=db_event.programs
    )