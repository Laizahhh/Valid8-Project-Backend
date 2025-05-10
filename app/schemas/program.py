from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from pydantic import computed_field
from app.schemas.department import Department

class ProgramBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, example="BS Computer Science")

class ProgramCreate(ProgramBase):
    department_ids: List[int] = Field(
        default_factory=list,
        description="List of department IDs this program belongs to"
    )

class ProgramUpdate(BaseModel):
    name: Optional[str] = Field(
        None, 
        min_length=2, 
        max_length=100,
        example="BS Information Technology"
    )
    department_ids: Optional[List[int]] = Field(
        None,
        description="List of department IDs this program belongs to"
    )

class Program(ProgramBase):
    id: int
    departments: List[Department] = Field(default_factory=list)
    
    @computed_field
    def department_ids(self) -> List[int]:
        return [d.id for d in self.departments]
    
    model_config = ConfigDict(from_attributes=True)

class ProgramWithRelations(Program):
    departments: List[Department] = Field(
        default_factory=list,
        description="Detailed department information"
    )
    
    model_config = ConfigDict(from_attributes=True)