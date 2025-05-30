from pydantic import BaseModel

class Role(BaseModel):
    id: int
    name: str
    
    class Config:
        from_attributes = True