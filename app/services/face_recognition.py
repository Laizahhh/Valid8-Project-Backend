import face_recognition
import numpy as np
import pickle
from typing import Optional

class FaceRecognitionService:
    def __init__(self):
        self.known_faces = {}  # student_id: encoding
        
    def register_face(self, student_id: str, image_path: str) -> bool:
        try:
            image = face_recognition.load_image_file(image_path)
            encodings = face_recognition.face_encodings(image)
            if not encodings:
                return False
            self.known_faces[student_id] = encodings[0]
            return True
        except Exception:
            return False
    
    def recognize_face(self, image_path: str) -> Optional[str]:
        try:
            unknown_image = face_recognition.load_image_file(image_path)
            unknown_encoding = face_recognition.face_encodings(unknown_image)
            if not unknown_encoding:
                return None
                
            for student_id, known_encoding in self.known_faces.items():
                results = face_recognition.compare_faces([known_encoding], unknown_encoding[0])
                if results[0]:
                    return student_id
            return None
        except Exception:
            return None
    
    def save_encodings(self, file_path: str):
        with open(file_path, 'wb') as f:
            pickle.dump(self.known_faces, f)
    
    def load_encodings(self, file_path: str):
        try:
            with open(file_path, 'rb') as f:
                self.known_faces = pickle.load(f)
        except FileNotFoundError:
            self.known_faces = {}