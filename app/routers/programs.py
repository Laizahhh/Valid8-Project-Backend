from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from typing import List
import logging

from app.database import get_db
from app.models.program import Program as ProgramModel
from app.models.department import Department as DepartmentModel
from app.schemas.program import Program, ProgramCreate, ProgramUpdate  # Removed ProgramWithRelations

router = APIRouter(prefix="/programs", tags=["programs"])
logger = logging.getLogger(__name__)

# 1. CREATE PROGRAM (Now returns flat structure)
@router.post("/", response_model=Program, status_code=status.HTTP_201_CREATED)
def create_program(program: ProgramCreate, db: Session = Depends(get_db)):
    try:
        program_name = program.name.strip()
        
        # Check for existing program
        if db.query(ProgramModel).filter(
            func.lower(ProgramModel.name) == func.lower(program_name)
        ).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Program '{program_name}' already exists"
            )

        new_program = ProgramModel(name=program_name)
        db.add(new_program)
        db.flush()  # Get ID before commit
        
        # Handle department associations (still needed for DB)
        if program.department_ids:
            departments = db.query(DepartmentModel).filter(
                DepartmentModel.id.in_(program.department_ids)
            ).all()
            
            if len(departments) != len(program.department_ids):
                missing = set(program.department_ids) - {d.id for d in departments}
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Departments not found: {missing}"
                )
            new_program.departments = departments
        
        db.commit()
        db.refresh(new_program)
        
        # Manually set department_ids for response
        new_program.department_ids = [d.id for d in new_program.departments]
        return new_program

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating program: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create program"
        )

# 2. READ ALL PROGRAMS (Flat)
@router.get("/", response_model=List[Program])
def read_programs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    try:
        programs = db.query(ProgramModel).offset(skip).limit(limit).all()
        # Add department_ids to each program
        for program in programs:
            program.department_ids = [d.id for d in program.departments]
        return programs
    except Exception as e:
        logger.error(f"Error fetching programs: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch programs"
        )

# 3. READ SINGLE PROGRAM (Flat)
@router.get("/{program_id}", response_model=Program)
def read_program(program_id: int, db: Session = Depends(get_db)):
    program = db.query(ProgramModel).get(program_id)
    if not program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program not found"
        )
    # Add department_ids
    program.department_ids = [d.id for d in program.departments]
    return program

# 4. UPDATE PROGRAM (Flat)
@router.patch("/{program_id}", response_model=Program)
def update_program(
    program_id: int,
    program_update: ProgramUpdate,
    db: Session = Depends(get_db)
):
    try:
        db_program = db.query(ProgramModel).get(program_id)
        if not db_program:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Program not found"
            )

        # Update name
        if program_update.name is not None:
            new_name = program_update.name.strip()
            if db.query(ProgramModel).filter(
                func.lower(ProgramModel.name) == func.lower(new_name),
                ProgramModel.id != program_id
            ).first():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Program '{new_name}' already exists"
                )
            db_program.name = new_name

        # Update departments (still needed for DB)
        if program_update.department_ids is not None:
            db_program.departments = []
            if program_update.department_ids:
                departments = db.query(DepartmentModel).filter(
                    DepartmentModel.id.in_(program_update.department_ids)
                ).all()
                if len(departments) != len(program_update.department_ids):
                    missing = set(program_update.department_ids) - {d.id for d in departments}
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Departments not found: {missing}"
                    )
                db_program.departments = departments
        
        db.commit()
        db.refresh(db_program)
        db_program.department_ids = [d.id for d in db_program.departments]
        return db_program

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating program: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update program"
        )


# 5. DELETE PROGRAM
@router.delete("/{program_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_program(program_id: int, db: Session = Depends(get_db)):
    try:
        program = db.query(ProgramModel).get(program_id)
        if not program:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Program not found"
            )

        db.delete(program)
        db.commit()
        return None

    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete program - it's referenced by other records"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting program: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete program"
        )