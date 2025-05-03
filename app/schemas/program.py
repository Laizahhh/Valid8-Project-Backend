# app/schemas/program.py
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.department import Department

class ProgramBase(BaseModel):
    name: str

class ProgramCreate(ProgramBase):
    department_ids: List[int] = []

class Program(ProgramBase):
    id: int
    department_ids: List[int] = []
    
    model_config = ConfigDict(from_attributes=True)

class ProgramWithRelations(Program):
    departments: List[Department] = []
    
    model_config = ConfigDict(from_attributes=True)