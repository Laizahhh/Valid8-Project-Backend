# app/routers/program.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import List
import logging

from app.database import get_db
from app.models.program import Program as ProgramModel
from app.models.department import Department as DepartmentModel
from app.schemas.program import Program, ProgramCreate, ProgramWithRelations

router = APIRouter(prefix="/programs", tags=["programs"])
logger = logging.getLogger(__name__)

@router.post("/", response_model=Program, status_code=status.HTTP_201_CREATED)
def create_program(program: ProgramCreate, db: Session = Depends(get_db)):
    try:
        # Normalize the program name first
        program_name = program.name.strip().lower()  # <-- Add this line
        logger.info(f"Attempting to create program: {program_name}")  # <-- Change to program_name

        # Check if program already exists with case-insensitive comparison
        existing_program = db.query(ProgramModel).filter(
            ProgramModel.name.ilike(program_name)  # <-- Change to program_name
        ).first()
        
        if existing_program:
            logger.warning(f"Program already exists: {program_name}")  # <-- Change to program_name
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Program with name '{program_name}' already exists"  # <-- Change to program_name
            )

        # Create new program instance with normalized name
        new_program = ProgramModel(name=program_name)  # <-- Change to program_name
        db.add(new_program)
        db.flush()
        
        # Rest of your function remains the same...
        if program.department_ids:
            logger.info(f"Looking up departments: {program.department_ids}")
            departments = db.query(DepartmentModel).filter(
                DepartmentModel.id.in_(program.department_ids)
            ).all()
            
            # Verify all departments exist
            if len(departments) != len(program.department_ids):
                found_ids = {d.id for d in departments}
                missing_ids = set(program.department_ids) - found_ids
                logger.warning(f"Missing departments: {missing_ids}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Departments not found: {missing_ids}"
                )
            
            # Clear existing relationships and set new ones
            new_program.departments = departments
            logger.info(f"Assigned departments: {[d.id for d in departments]}")
        
        # Commit transaction
        db.commit()
        db.refresh(new_program)
        
        # Log database state after commit
        logger.info(f"Database state after commit:")
        logger.info(f"Program ID: {new_program.id}, Name: {new_program.name}")
        logger.info(f"Associated department IDs: {[d.id for d in new_program.departments]}")
        
        # Create response
        result = Program(
            id=new_program.id,
            name=new_program.name,
            department_ids=[d.id for d in new_program.departments]
        )
        
        logger.info(f"Successfully created program: {result.name} (ID: {result.id})")
        logger.info(f"Response department_ids: {result.department_ids}")
        
        return result

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error creating program: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Program creation failed (possible duplicate name)"
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating program: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while creating program"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error creating program: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@router.get("/", response_model=List[Program])
def read_programs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    programs = db.query(ProgramModel).offset(skip).limit(limit).all()
    
    # Log the actual database contents
    for program in programs:
        logger.info(f"Program ID: {program.id}, Name: {program.name}")
        logger.info(f"Department IDs: {[d.id for d in program.departments]}")
    
    # Create response objects with explicit department_ids
    results = []
    for program in programs:
        results.append(Program(
            id=program.id,
            name=program.name,
            department_ids=[d.id for d in program.departments]
        ))
    
    return results

@router.get("/{program_id}", response_model=ProgramWithRelations)
def read_program(program_id: int, db: Session = Depends(get_db)):
    program = db.query(ProgramModel).filter(ProgramModel.id == program_id).first()
    if not program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program not found"
        )
    
    # Log actual relationships from database
    logger.info(f"Retrieved program: ID={program.id}, Name={program.name}")
    logger.info(f"Associated departments: {[d.id for d in program.departments]}")
    
    # Create response with explicitly loaded relationships
    return ProgramWithRelations(
        id=program.id,
        name=program.name,
        department_ids=[d.id for d in program.departments],
        departments=program.departments
    )