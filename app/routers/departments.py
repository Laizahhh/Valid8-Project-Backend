from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
import logging

from app.database import get_db
from app.models.department import Department as DepartmentModel
from app.schemas.department import (
    Department as DepartmentSchema,
    DepartmentCreate,
    DepartmentUpdate
)

router = APIRouter(prefix="/departments", tags=["departments"])
logger = logging.getLogger(__name__)

@router.post(
    "/",
    response_model=DepartmentSchema,
    status_code=status.HTTP_201_CREATED
)
def create_department(
    department: DepartmentCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new department.
    
    - **name**: Department name (must be unique, 2-100 characters)
    """
    try:
        # Check for existing department (case-insensitive)
        existing = db.query(DepartmentModel).filter(
            func.lower(DepartmentModel.name) == func.lower(department.name.strip())
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Department with this name already exists"
            )

        db_department = DepartmentModel(name=department.name.strip())
        db.add(db_department)
        db.commit()
        db.refresh(db_department)
        return db_department

    except IntegrityError:
        db.rollback()
        logger.error("Integrity error creating department", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department creation failed - possible duplicate name"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error creating department: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create department"
        )

@router.get("/", response_model=list[DepartmentSchema])
def read_departments(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=1000, description="Pagination limit"),
    db: Session = Depends(get_db)
):
    """
    Retrieve list of departments with pagination.
    
    - **skip**: Number of records to skip
    - **limit**: Maximum number of records to return (1-1000)
    """
    try:
        return db.query(DepartmentModel).offset(skip).limit(limit).all()
    except Exception as e:
        logger.error(f"Error fetching departments: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve departments"
        )

@router.get("/{department_id}", response_model=DepartmentSchema)
def read_department(
    department_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a single department by ID.
    
    - **department_id**: ID of the department to retrieve
    """
    db_department = db.query(DepartmentModel).get(department_id)
    if not db_department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    return db_department

@router.patch("/{department_id}", response_model=DepartmentSchema)
def update_department(
    department_id: int,
    department_update: DepartmentUpdate,
    db: Session = Depends(get_db)
):
    """
    Update department information.
    
    - **department_id**: ID of the department to update
    - **name**: New department name (optional)
    """
    try:
        db_department = db.query(DepartmentModel).get(department_id)
        if not db_department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found"
            )

        if department_update.name is not None:
            # Check for name conflicts
            existing = db.query(DepartmentModel).filter(
                func.lower(DepartmentModel.name) == func.lower(department_update.name.strip()),
                DepartmentModel.id != department_id
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Department with this name already exists"
                )
            db_department.name = department_update.name.strip()

        db.commit()
        db.refresh(db_department)
        return db_department

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating department: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update department"
        )

@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    department_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a department.
    
    - **department_id**: ID of the department to delete
    """
    try:
        db_department = db.query(DepartmentModel).get(department_id)
        if not db_department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found"
            )

        db.delete(db_department)
        db.commit()
        return None

    except IntegrityError:
        db.rollback()
        logger.error("Integrity error deleting department", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete department - it may be referenced by programs"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting department: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete department"
        )