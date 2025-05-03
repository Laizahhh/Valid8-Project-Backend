from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import users, events, programs, departments, auth 
from app.services.face_recognition import FaceRecognitionService


app = FastAPI()

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users.router)
app.include_router(events.router)
app.include_router(programs.router)
app.include_router(departments.router)
app.include_router(auth.router)

# Load face encodings at startup
face_service = FaceRecognitionService()
face_service.load_encodings("face_encodings.pkl")

@app.get("/")
async def root():
    return {
        "message": "Welcome to the Student Attendance System API",
        "endpoints": {
            "users": "/users",
            "events": "/events",
            "programs": "/programs",
            "departments": "/departments"
        }
    }

@app.on_event("shutdown")
def save_face_encodings():
    face_service.save_encodings("face_encodings.pkl")