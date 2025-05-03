# app/routers/department.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.schemas.department import Department as DepartmentSchema
from app.schemas.department import DepartmentCreate
from app.models.department import Department as DepartmentModel
from app.database import get_db
import logging

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/departments", tags=["departments"])

@router.post("/", response_model=DepartmentSchema)
def create_department(department: DepartmentCreate, db: Session = Depends(get_db)):
    try:
        logger.info(f"Creating department: {department.name}")
        db_department = DepartmentModel(name=department.name)
        db.add(db_department)
        db.commit()
        db.refresh(db_department)
        logger.info(f"Department created successfully: ID={db_department.id}")
        return db_department
    except IntegrityError as e:
        db.rollback()
        logger.error(f"IntegrityError creating department: {str(e)}")
        raise HTTPException(status_code=400, detail="Department with this name already exists")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating department: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@router.get("/", response_model=list[DepartmentSchema])
def read_departments(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    departments = db.query(DepartmentModel).offset(skip).limit(limit).all()
    return departments

@router.get("/{department_id}", response_model=DepartmentSchema)
def read_department(department_id: int, db: Session = Depends(get_db)):
    db_department = db.query(DepartmentModel).filter(DepartmentModel.id == department_id).first()
    if db_department is None:
        raise HTTPException(status_code=404, detail="Department not found")
    return db_department
