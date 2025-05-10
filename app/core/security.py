from datetime import datetime, timedelta
from typing import Optional, List
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.auth import TokenData

# Configuration - use environment variables in production!
SECRET_KEY = "your-strong-secret-key"  # Change this!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="token",
    scopes={
        "read": "Read access",
        "write": "Write access"
    }
)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate user with email and password"""
    user = db.query(User)\
             .options(joinedload(User.roles).joinedload(UserRole.role))\
             .filter(User.email == email)\
             .first()
    
    if not user or not verify_password(password, user.password_hash):
        return None
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT token with expiration"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Get current user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    
    user = db.query(User)\
             .options(joinedload(User.roles).joinedload(UserRole.role))\
             .filter(User.email == token_data.email)\
             .first()
    
    if user is None:
        raise credentials_exception
    return user

async def get_current_user_with_roles(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current user from JWT token with all roles and profiles loaded.
    Similar to get_current_user but ensures all relationships are eagerly loaded.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    
    # Load user with all the relevant relationships
    user = db.query(User)\
             .options(
                 joinedload(User.roles).joinedload(UserRole.role),
                 joinedload(User.student_profile),
                 joinedload(User.ssg_profile)
             )\
             .filter(User.email == token_data.email)\
             .first()
    
    if user is None:
        raise credentials_exception
    return user

async def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """Dependency to validate admin role"""
    if not any(role.role.name == "admin" for role in current_user.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,  # Use 403 instead of 401
            detail="Admin privileges required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return current_user

# New role-based dependency helpers
async def get_current_ssg(
    current_user: User = Depends(get_current_user_with_roles)
) -> User:
    """Dependency to validate SSG role"""
    if not any(role.role.name == "ssg" for role in current_user.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SSG privileges required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return current_user

async def get_current_event_organizer(
    current_user: User = Depends(get_current_user_with_roles)
) -> User:
    """Dependency to validate event-organizer role"""
    if not any(role.role.name == "event-organizer" for role in current_user.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Event organizer privileges required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return current_user

async def get_user_with_required_roles(
    required_roles: List[str],
    current_user: User = Depends(get_current_user_with_roles)
) -> User:
    """
    Dependency to validate if user has any of the required roles
    
    Args:
        required_roles: List of role names, one of which the user must have
        current_user: Current authenticated user
        
    Returns:
        User if they have one of the required roles
        
    Raises:
        HTTPException: If user doesn't have any of the required roles
    """
    user_roles = set(role.role.name for role in current_user.roles)
    if not any(role in user_roles for role in required_roles):
        role_str = ", ".join(required_roles)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Required roles: {role_str}",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return current_user