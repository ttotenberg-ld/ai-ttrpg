from datetime import datetime, timedelta, timezone
from typing import Optional
import os
import secrets
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlmodel import Session, select

from database import engine
from models import User, UserSession, PasswordResetToken

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))  # Generate a secure random key if not set
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Account lockout configuration
MAX_LOGIN_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
LOCKOUT_DURATION_MINUTES = int(os.getenv("LOCKOUT_DURATION_MINUTES", "15"))

# Password reset configuration
PASSWORD_RESET_TOKEN_EXPIRE_HOURS = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_HOURS", "1"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token() -> str:
    """Generate a unique refresh token using UUID4"""
    return str(uuid.uuid4())

def create_user_session(user_id: int, session: Session) -> UserSession:
    """Create a new user session with refresh token"""
    refresh_token = create_refresh_token()
    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    user_session = UserSession(
        user_id=user_id,
        refresh_token=refresh_token,
        expires_at=expires_at
    )
    
    session.add(user_session)
    session.commit()
    session.refresh(user_session)
    return user_session

def validate_refresh_token(refresh_token: str, session: Session) -> Optional[UserSession]:
    """Validate a refresh token and return the associated user session if valid"""
    user_session = session.exec(
        select(UserSession).where(
            UserSession.refresh_token == refresh_token,
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        )
    ).first()
    
    return user_session

def blacklist_refresh_token(refresh_token: str, session: Session) -> bool:
    """Blacklist a refresh token by setting is_active to False"""
    user_session = session.exec(
        select(UserSession).where(UserSession.refresh_token == refresh_token)
    ).first()
    
    if user_session:
        user_session.is_active = False
        session.add(user_session)
        session.commit()
        return True
    return False

def cleanup_expired_sessions(session: Session) -> int:
    """Remove expired user sessions from the database"""
    expired_sessions = session.exec(
        select(UserSession).where(UserSession.expires_at <= datetime.utcnow())
    ).all()
    
    count = len(expired_sessions)
    for expired_session in expired_sessions:
        session.delete(expired_session)
    
    session.commit()
    return count

def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == username)).first()
        if user is None:
            raise credentials_exception
        
        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Inactive user",
            )
        
        # Check if account lockout has expired and unlock if needed
        unlock_account_if_expired(user, session)
        
        # Check if account is currently locked
        if is_account_locked(user):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account temporarily locked",
            )
        
        return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user with additional checks"""
    return current_user 

def check_and_handle_account_lockout(user: User, session: Session) -> None:
    """
    Check if user should be locked out after failed login attempts.
    Lock the account if maximum attempts reached.
    """
    if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
        # Lock the account for the configured duration
        lockout_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        user.locked_until = lockout_until
        user.updated_at = datetime.utcnow()
        session.add(user)
        session.commit()
        print(f"Account locked for user {user.username} until {lockout_until}")

def is_account_locked(user: User) -> bool:
    """Check if user account is currently locked"""
    if user.locked_until and user.locked_until > datetime.utcnow():
        return True
    return False

def unlock_account_if_expired(user: User, session: Session) -> bool:
    """
    Unlock account if lockout period has expired.
    Returns True if account was unlocked, False otherwise.
    """
    if user.locked_until and user.locked_until <= datetime.utcnow():
        user.locked_until = None
        user.failed_login_attempts = 0
        user.updated_at = datetime.utcnow()
        session.add(user)
        session.commit()
        print(f"Account automatically unlocked for user {user.username}")
        return True
    return False

def generate_password_reset_token() -> str:
    """Generate a secure password reset token using secrets"""
    return secrets.token_urlsafe(32)

def create_password_reset_token(user_id: int, session: Session) -> PasswordResetToken:
    """Create a new password reset token for a user"""
    # Invalidate any existing unused password reset tokens for this user
    existing_tokens = session.exec(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.is_used == False,
            PasswordResetToken.expires_at > datetime.utcnow()
        )
    ).all()
    
    for token in existing_tokens:
        token.is_used = True
        session.add(token)
    
    # Create new password reset token
    reset_token = generate_password_reset_token()
    expires_at = datetime.utcnow() + timedelta(hours=PASSWORD_RESET_TOKEN_EXPIRE_HOURS)
    
    password_reset_token = PasswordResetToken(
        user_id=user_id,
        token=reset_token,
        expires_at=expires_at
    )
    
    session.add(password_reset_token)
    session.commit()
    session.refresh(password_reset_token)
    return password_reset_token

def validate_password_reset_token(token: str, session: Session) -> Optional[PasswordResetToken]:
    """Validate a password reset token and return it if valid"""
    password_reset_token = session.exec(
        select(PasswordResetToken).where(
            PasswordResetToken.token == token,
            PasswordResetToken.is_used == False,
            PasswordResetToken.expires_at > datetime.utcnow()
        )
    ).first()
    
    return password_reset_token

def mark_password_reset_token_as_used(token: str, session: Session) -> bool:
    """Mark a password reset token as used"""
    password_reset_token = session.exec(
        select(PasswordResetToken).where(PasswordResetToken.token == token)
    ).first()
    
    if password_reset_token:
        password_reset_token.is_used = True
        session.add(password_reset_token)
        session.commit()
        return True
    return False

def cleanup_expired_password_reset_tokens(session: Session) -> int:
    """Remove expired password reset tokens from the database"""
    expired_tokens = session.exec(
        select(PasswordResetToken).where(PasswordResetToken.expires_at <= datetime.utcnow())
    ).all()
    
    count = len(expired_tokens)
    for expired_token in expired_tokens:
        session.delete(expired_token)
    
    session.commit()
    return count 