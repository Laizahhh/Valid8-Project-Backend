from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

class DepartmentBase(BaseModel):
    name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        examples=["Computer Science", "Engineering"],
        description="Official name of the department"
    )

class DepartmentCreate(DepartmentBase):
    pass

class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(
        None,
        min_length=2,
        max_length=100,
        examples=["Updated Department Name"],
        description="New name for the department"
    )

class Department(DepartmentBase):
    id: int = Field(..., description="Unique identifier of the department")
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "Computer Science"
            }
        }
    )