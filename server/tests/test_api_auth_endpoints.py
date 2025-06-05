#!/usr/bin/env python3
"""
API Endpoint Tests for Authentication System - Task 5.9
Create API endpoint tests for all new authentication endpoints

This test suite comprehensively tests all authentication API endpoints including:
- POST /users/ - User registration
- POST /token - User login (OAuth2 password flow)
- POST /auth/refresh - Token refresh
- POST /auth/logout - User logout
- POST /auth/forgot-password - Password reset request
- POST /auth/reset-password - Password reset completion
- POST /auth/cleanup-sessions - Session cleanup (admin)
- GET /auth/password-policy - Password policy info
- GET /users/profile - Get user profile
- PATCH /users/profile - Update user profile
- GET /users/me/ - Get current user info
"""

import pytest
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.testclient import TestClient
from sqlmodel import Session, select, create_engine, SQLModel
from sqlmodel.pool import StaticPool

# Add server directory to path for imports
server_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, server_dir)

# Import only what we need for auth testing
from models import User, UserSession, PasswordResetToken, UserCreate, UserProfile, UserProfileUpdate
from auth import (
    get_password_hash, verify_password, create_access_token, create_user_session,
    validate_refresh_token, blacklist_refresh_token, cleanup_expired_sessions,
    create_password_reset_token, validate_password_reset_token, 
    mark_password_reset_token_as_used, cleanup_expired_password_reset_tokens,
    get_current_active_user, unlock_account_if_expired, is_account_locked,
    check_and_handle_account_lockout, ACCESS_TOKEN_EXPIRE_MINUTES
)
from middleware.password_validator import validate_password_strength, get_password_policy

# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

def get_test_session():
    """Override database session for testing"""
    with Session(test_engine) as session:
        yield session

# Create a minimal test app with only auth endpoints
test_app = FastAPI()

# Response models
class TokenResponse(SQLModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshTokenRequest(SQLModel):
    refresh_token: str

class LogoutRequest(SQLModel):
    refresh_token: str

class MessageResponse(SQLModel):
    message: str

class ForgotPasswordRequest(SQLModel):
    email: str

class ResetPasswordRequest(SQLModel):
    token: str
    new_password: str

class PasswordPolicyResponse(SQLModel):
    min_length: int
    max_length: int
    requirements: dict
    restrictions: dict

class UserResponse(SQLModel):
    id: int
    username: str
    email: str
    email_verified: bool
    is_active: bool
    failed_login_attempts: int
    locked_until: Optional[datetime] = None
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

# Auth endpoints for testing
@test_app.post("/users/", response_model=UserResponse)
async def create_user(user: UserCreate, session: Session = Depends(get_test_session)):
    db_user = session.exec(select(User).where(User.username == user.username)).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    db_user_email = session.exec(select(User).where(User.email == user.email)).first()
    if db_user_email:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Validate password strength
    password_result = validate_password_strength(user.password, user.username, user.email)
    if not password_result.is_valid:
        raise HTTPException(
            status_code=400, 
            detail={
                "message": "Password does not meet security requirements",
                "errors": password_result.errors,
                "suggestions": password_result.suggestions,
                "strength_score": password_result.score,
                "strength_level": password_result.strength_level
            }
        )
    
    hashed_password = get_password_hash(user.password)
    db_user = User(username=user.username, email=user.email, hashed_password=hashed_password)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user

@test_app.post("/token", response_model=TokenResponse)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_test_session)):
    user = session.exec(select(User).where(User.username == form_data.username)).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if account lockout has expired and unlock if needed
    unlock_account_if_expired(user, session)
    
    # Check if account is currently locked
    if is_account_locked(user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account temporarily locked due to too many failed login attempts. Please try again later.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify password
    if not verify_password(form_data.password, user.hashed_password):
        # Increment failed login attempts
        user.failed_login_attempts += 1
        user.updated_at = datetime.utcnow()
        
        # Check if this failed attempt should trigger account lockout
        check_and_handle_account_lockout(user, session)
        
        # Determine error message based on whether account was just locked
        from auth import MAX_LOGIN_ATTEMPTS
        if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
            detail_msg = "Account locked due to too many failed login attempts. Please try again later."
        else:
            remaining_attempts = MAX_LOGIN_ATTEMPTS - user.failed_login_attempts
            detail_msg = f"Incorrect username or password. {remaining_attempts} attempt(s) remaining before account lockout."
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail_msg,
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Successful login - reset failed attempts and update last_login
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.utcnow()
    user.updated_at = datetime.utcnow()
    session.add(user)
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    # Create refresh token session
    user_session = create_user_session(user.id, session)
    
    # Clean up expired sessions periodically
    cleanup_expired_sessions(session)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=user_session.refresh_token
    )

@test_app.post("/auth/logout", response_model=MessageResponse)
async def logout(logout_request: LogoutRequest, session: Session = Depends(get_test_session)):
    """Logout user by blacklisting their refresh token"""
    success = blacklist_refresh_token(logout_request.refresh_token, session)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid refresh token"
        )
    return MessageResponse(message="Successfully logged out")

@test_app.post("/auth/refresh", response_model=TokenResponse)
async def refresh_access_token(refresh_request: RefreshTokenRequest, session: Session = Depends(get_test_session)):
    """Generate new access and refresh tokens using a valid refresh token"""
    # Validate the refresh token
    user_session = validate_refresh_token(refresh_request.refresh_token, session)
    if not user_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get the user associated with the session
    user = session.get(User, user_session.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user account is locked
    if user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account temporarily locked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Blacklist the old refresh token
    blacklist_refresh_token(refresh_request.refresh_token, session)
    
    # Create new access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    # Create new refresh token session
    new_user_session = create_user_session(user.id, session)
    
    # Clean up expired sessions
    cleanup_expired_sessions(session)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_user_session.refresh_token
    )

@test_app.post("/auth/forgot-password", response_model=MessageResponse)
async def forgot_password(request: ForgotPasswordRequest, session: Session = Depends(get_test_session)):
    """Request a password reset token for the given email address"""
    user = session.exec(select(User).where(User.email == request.email)).first()
    
    # Always return success message to prevent email enumeration attacks
    if not user:
        return MessageResponse(message="If an account with that email exists, a password reset link has been sent.")
    
    # Check if user account is active
    if not user.is_active:
        return MessageResponse(message="If an account with that email exists, a password reset link has been sent.")
    
    # Create password reset token
    reset_token = create_password_reset_token(user.id, session)
    
    # Clean up expired password reset tokens periodically
    cleanup_expired_password_reset_tokens(session)
    
    return MessageResponse(message="If an account with that email exists, a password reset link has been sent.")

@test_app.post("/auth/reset-password", response_model=MessageResponse)
async def reset_password(request: ResetPasswordRequest, session: Session = Depends(get_test_session)):
    """Reset user password using a valid password reset token"""
    # Validate the password reset token
    reset_token = validate_password_reset_token(request.token, session)
    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token"
        )
    
    # Get the user associated with the token
    user = session.get(User, reset_token.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token"
        )
    
    # Validate new password strength
    password_result = validate_password_strength(request.new_password, user.username, user.email)
    if not password_result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Password does not meet security requirements",
                "errors": password_result.errors,
                "suggestions": password_result.suggestions,
                "strength_score": password_result.score,
                "strength_level": password_result.strength_level
            }
        )
    
    # Update user password
    user.hashed_password = get_password_hash(request.new_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    user.updated_at = datetime.utcnow()
    session.add(user)
    
    # Mark the password reset token as used
    mark_password_reset_token_as_used(request.token, session)
    
    # Invalidate all existing user sessions for security
    existing_sessions = session.exec(
        select(UserSession).where(
            UserSession.user_id == user.id,
            UserSession.is_active == True
        )
    ).all()
    
    for user_session in existing_sessions:
        user_session.is_active = False
        session.add(user_session)
    
    session.commit()
    
    return MessageResponse(message="Password has been successfully reset. Please log in with your new password.")

@test_app.get("/auth/password-policy", response_model=PasswordPolicyResponse)
async def get_password_policy_info():
    """Get current password policy requirements"""
    policy = get_password_policy()
    return PasswordPolicyResponse(**policy)

@test_app.post("/auth/cleanup-sessions", response_model=MessageResponse)
async def cleanup_expired_user_sessions(session: Session = Depends(get_test_session)):
    """Administrative endpoint to clean up expired user sessions"""
    cleaned_count = cleanup_expired_sessions(session)
    return MessageResponse(message=f"Cleaned up {cleaned_count} expired sessions")

@test_app.get("/users/profile", response_model=UserProfile)
async def get_user_profile(current_user: User = Depends(get_current_active_user)):
    """Get current user's profile information"""
    return UserProfile(
        username=current_user.username,
        email=current_user.email,
        email_verified=current_user.email_verified,
        is_active=current_user.is_active,
        last_login=current_user.last_login,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at
    )

@test_app.patch("/users/profile", response_model=UserProfile)
async def update_user_profile(
    profile_update: UserProfileUpdate,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_test_session)
):
    """Update current user's profile information"""
    # Get the user from the database to ensure we have the latest data
    user = session.get(User, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get the update data, excluding unset fields
    update_data = profile_update.model_dump(exclude_unset=True)
    
    # Validate and apply updates
    for field, value in update_data.items():
        if field == "username":
            if value and len(value.strip()) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username cannot be empty"
                )
            
            # Check if username is already taken by another user
            existing_user = session.exec(
                select(User).where(User.username == value, User.id != user.id)
            ).first()
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken"
                )
            
            user.username = value.strip()
        
        elif field == "email":
            if value and len(value.strip()) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email cannot be empty"
                )
            
            # Basic email validation
            if value and "@" not in value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid email format"
                )
            
            # Check if email is already taken by another user
            existing_user = session.exec(
                select(User).where(User.email == value, User.id != user.id)
            ).first()
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already taken"
                )
            
            # If email is being changed, mark as unverified
            if value != user.email:
                user.email_verified = False
            
            user.email = value.strip()
    
    # Update the updated_at timestamp
    user.updated_at = datetime.utcnow()
    
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # Return updated profile
    return UserProfile(
        username=user.username,
        email=user.email,
        email_verified=user.email_verified,
        is_active=user.is_active,
        last_login=user.last_login,
        created_at=user.created_at,
        updated_at=user.updated_at
    )

@test_app.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

# Create test client
client = TestClient(test_app)

@pytest.fixture(scope="function")
def test_db():
    """Create test database for each test"""
    SQLModel.metadata.create_all(test_engine)
    yield
    SQLModel.metadata.drop_all(test_engine)

@pytest.fixture
def test_user_data():
    """Sample user data for testing"""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "SecurePhrase123!"
    }

@pytest.fixture
def weak_password_user_data():
    """User data with weak password for testing"""
    return {
        "username": "weakuser",
        "email": "weak@example.com",
        "password": "123"
    }

@pytest.fixture
def registered_user(test_db, test_user_data):
    """Create a registered user for testing"""
    response = client.post("/users/", json=test_user_data)
    assert response.status_code == 200
    return response.json()

@pytest.fixture
def logged_in_user(test_db, test_user_data):
    """Create and login a user, return tokens"""
    # Register user
    client.post("/users/", json=test_user_data)
    
    # Login user
    login_response = client.post("/token", data={
        "username": test_user_data["username"],
        "password": test_user_data["password"]
    })
    assert login_response.status_code == 200
    return login_response.json()


class TestUserRegistrationEndpoint:
    """Test POST /users/ endpoint for user registration"""
    
    def test_register_success(self, test_db, test_user_data):
        """Test successful user registration"""
        response = client.post("/users/", json=test_user_data)
        
        # Debug output
        if response.status_code != 200:
            print(f"Response status: {response.status_code}")
            print(f"Response content: {response.content}")
            print(f"Response JSON: {response.json()}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == test_user_data["username"]
        assert data["email"] == test_user_data["email"]
        assert data["is_active"] is True
        assert data["email_verified"] is False
        assert "hashed_password" not in data  # Password should not be returned
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_register_duplicate_username(self, test_db, test_user_data):
        """Test registration with duplicate username"""
        # Register first user
        client.post("/users/", json=test_user_data)
        
        # Try to register with same username but different email
        duplicate_data = test_user_data.copy()
        duplicate_data["email"] = "different@example.com"
        
        response = client.post("/users/", json=duplicate_data)
        
        assert response.status_code == 400
        assert "Username already registered" in response.json()["detail"]
    
    def test_register_duplicate_email(self, test_db, test_user_data):
        """Test registration with duplicate email"""
        # Register first user
        client.post("/users/", json=test_user_data)
        
        # Try to register with same email but different username
        duplicate_data = test_user_data.copy()
        duplicate_data["username"] = "differentuser"
        
        response = client.post("/users/", json=duplicate_data)
        
        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]
    
    def test_register_weak_password(self, test_db, weak_password_user_data):
        """Test registration with weak password"""
        response = client.post("/users/", json=weak_password_user_data)
        
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "Password does not meet security requirements" in detail["message"]
        assert "errors" in detail
        assert "suggestions" in detail
        assert "strength_score" in detail
        assert "strength_level" in detail
    
    def test_register_missing_fields(self, test_db):
        """Test registration with missing required fields"""
        # Missing username
        response = client.post("/users/", json={
            "email": "test@example.com",
            "password": "SecurePassword123!"
        })
        assert response.status_code == 422
        
        # Missing email
        response = client.post("/users/", json={
            "username": "testuser",
            "password": "SecurePassword123!"
        })
        assert response.status_code == 422
        
        # Missing password
        response = client.post("/users/", json={
            "username": "testuser",
            "email": "test@example.com"
        })
        assert response.status_code == 422
    
    def test_register_invalid_email_format(self, test_db):
        """Test registration with invalid email format"""
        response = client.post("/users/", json={
            "username": "testuser",
            "email": "invalid-email",
            "password": "SecurePassword123!"
        })
        assert response.status_code == 422


class TestLoginEndpoint:
    """Test POST /token endpoint for user login"""
    
    def test_login_success(self, test_db, test_user_data, registered_user):
        """Test successful user login"""
        response = client.post("/token", data={
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 50  # JWT tokens are long
        assert len(data["refresh_token"]) > 30  # UUID format
    
    def test_login_invalid_username(self, test_db, test_user_data, registered_user):
        """Test login with invalid username"""
        response = client.post("/token", data={
            "username": "nonexistentuser",
            "password": test_user_data["password"]
        })
        
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]
    
    def test_login_invalid_password(self, test_db, test_user_data, registered_user):
        """Test login with invalid password"""
        response = client.post("/token", data={
            "username": test_user_data["username"],
            "password": "wrongpassword"
        })
        
        assert response.status_code == 401
        detail = response.json()["detail"]
        assert "Incorrect username or password" in detail
        assert "attempt(s) remaining" in detail
    
    def test_login_account_lockout(self, test_db, test_user_data, registered_user):
        """Test account lockout after multiple failed attempts"""
        # Make multiple failed login attempts
        for i in range(5):
            response = client.post("/token", data={
                "username": test_user_data["username"],
                "password": "wrongpassword"
            })
            assert response.status_code == 401
        
        # Next attempt should show account locked
        response = client.post("/token", data={
            "username": test_user_data["username"],
            "password": "wrongpassword"
        })
        
        assert response.status_code == 401
        assert "Account locked" in response.json()["detail"]
    
    def test_login_missing_credentials(self, test_db):
        """Test login with missing credentials"""
        # Missing username
        response = client.post("/token", data={
            "password": "password123"
        })
        assert response.status_code == 422
        
        # Missing password
        response = client.post("/token", data={
            "username": "testuser"
        })
        assert response.status_code == 422


class TestTokenRefreshEndpoint:
    """Test POST /auth/refresh endpoint for token refresh"""
    
    def test_refresh_success(self, test_db, logged_in_user):
        """Test successful token refresh"""
        refresh_token = logged_in_user["refresh_token"]
        
        response = client.post("/auth/refresh", json={
            "refresh_token": refresh_token
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        # New tokens should be different from original
        assert data["access_token"] != logged_in_user["access_token"]
        assert data["refresh_token"] != logged_in_user["refresh_token"]
    
    def test_refresh_invalid_token(self, test_db):
        """Test refresh with invalid token"""
        response = client.post("/auth/refresh", json={
            "refresh_token": "invalid-token"
        })
        
        assert response.status_code == 401
        assert "Invalid or expired refresh token" in response.json()["detail"]
    
    def test_refresh_expired_token(self, test_db, test_user_data):
        """Test refresh with expired token"""
        # Register and login user
        client.post("/users/", json=test_user_data)
        login_response = client.post("/token", data={
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        })
        
        # Manually expire the refresh token in database
        with Session(test_engine) as session:
            user = session.exec(select(User).where(User.username == test_user_data["username"])).first()
            user_session = session.exec(select(UserSession).where(UserSession.user_id == user.id)).first()
            user_session.expires_at = datetime.utcnow() - timedelta(hours=1)
            session.add(user_session)
            session.commit()
        
        response = client.post("/auth/refresh", json={
            "refresh_token": login_response.json()["refresh_token"]
        })
        
        assert response.status_code == 401
        assert "Invalid or expired refresh token" in response.json()["detail"]
    
    def test_refresh_missing_token(self, test_db):
        """Test refresh with missing token"""
        response = client.post("/auth/refresh", json={})
        assert response.status_code == 422


class TestLogoutEndpoint:
    """Test POST /auth/logout endpoint for user logout"""
    
    def test_logout_success(self, test_db, logged_in_user):
        """Test successful logout"""
        refresh_token = logged_in_user["refresh_token"]
        
        response = client.post("/auth/logout", json={
            "refresh_token": refresh_token
        })
        
        assert response.status_code == 200
        assert "Successfully logged out" in response.json()["message"]
        
        # Verify token is blacklisted by trying to use it
        refresh_response = client.post("/auth/refresh", json={
            "refresh_token": refresh_token
        })
        assert refresh_response.status_code == 401
    
    def test_logout_invalid_token(self, test_db):
        """Test logout with invalid token"""
        response = client.post("/auth/logout", json={
            "refresh_token": "invalid-token"
        })
        
        assert response.status_code == 400
        assert "Invalid refresh token" in response.json()["detail"]
    
    def test_logout_missing_token(self, test_db):
        """Test logout with missing token"""
        response = client.post("/auth/logout", json={})
        assert response.status_code == 422


class TestPasswordResetEndpoints:
    """Test password reset flow endpoints"""
    
    def test_forgot_password_success(self, test_db, test_user_data, registered_user):
        """Test successful password reset request"""
        response = client.post("/auth/forgot-password", json={
            "email": test_user_data["email"]
        })
        
        assert response.status_code == 200
        assert "password reset link has been sent" in response.json()["message"]
        
        # Verify reset token was created in database
        with Session(test_engine) as session:
            user = session.exec(select(User).where(User.email == test_user_data["email"])).first()
            reset_token = session.exec(
                select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
            ).first()
            assert reset_token is not None
            assert reset_token.is_used is False
            assert reset_token.expires_at > datetime.utcnow()
    
    def test_forgot_password_nonexistent_email(self, test_db):
        """Test password reset request for nonexistent email"""
        response = client.post("/auth/forgot-password", json={
            "email": "nonexistent@example.com"
        })
        
        # Should still return success to prevent email enumeration
        assert response.status_code == 200
        assert "password reset link has been sent" in response.json()["message"]
    
    def test_forgot_password_missing_email(self, test_db):
        """Test password reset request with missing email"""
        response = client.post("/auth/forgot-password", json={})
        assert response.status_code == 422
    
    def test_reset_password_success(self, test_db, test_user_data, registered_user):
        """Test successful password reset"""
        # First request password reset
        client.post("/auth/forgot-password", json={
            "email": test_user_data["email"]
        })
        
        # Get the reset token from database
        with Session(test_engine) as session:
            user = session.exec(select(User).where(User.email == test_user_data["email"])).first()
            reset_token = session.exec(
                select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
            ).first()
            token = reset_token.token
        
        # Reset password
        new_password = "NewSecurePassword123!"
        response = client.post("/auth/reset-password", json={
            "token": token,
            "new_password": new_password
        })
        
        assert response.status_code == 200
        assert "Password has been successfully reset" in response.json()["message"]
        
        # Verify can login with new password
        login_response = client.post("/token", data={
            "username": test_user_data["username"],
            "password": new_password
        })
        assert login_response.status_code == 200
        
        # Verify cannot login with old password
        old_login_response = client.post("/token", data={
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        })
        assert old_login_response.status_code == 401
    
    def test_reset_password_invalid_token(self, test_db):
        """Test password reset with invalid token"""
        response = client.post("/auth/reset-password", json={
            "token": "invalid-token",
            "new_password": "NewSecurePassword123!"
        })
        
        assert response.status_code == 400
        assert "Invalid or expired password reset token" in response.json()["detail"]
    
    def test_reset_password_weak_password(self, test_db, test_user_data, registered_user):
        """Test password reset with weak password"""
        # Request password reset
        client.post("/auth/forgot-password", json={
            "email": test_user_data["email"]
        })
        
        # Get reset token
        with Session(test_engine) as session:
            user = session.exec(select(User).where(User.email == test_user_data["email"])).first()
            reset_token = session.exec(
                select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
            ).first()
            token = reset_token.token
        
        # Try to reset with weak password
        response = client.post("/auth/reset-password", json={
            "token": token,
            "new_password": "123"
        })
        
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "Password does not meet security requirements" in detail["message"]
    
    def test_reset_password_expired_token(self, test_db, test_user_data, registered_user):
        """Test password reset with expired token"""
        # Create expired reset token manually
        with Session(test_engine) as session:
            user = session.exec(select(User).where(User.email == test_user_data["email"])).first()
            expired_token = PasswordResetToken(
                user_id=user.id,
                token="expired-token-123",
                expires_at=datetime.utcnow() - timedelta(hours=1),
                is_used=False
            )
            session.add(expired_token)
            session.commit()
        
        response = client.post("/auth/reset-password", json={
            "token": "expired-token-123",
            "new_password": "NewSecurePassword123!"
        })
        
        assert response.status_code == 400
        assert "Invalid or expired password reset token" in response.json()["detail"]


class TestPasswordPolicyEndpoint:
    """Test GET /auth/password-policy endpoint"""
    
    def test_get_password_policy(self, test_db):
        """Test getting password policy information"""
        response = client.get("/auth/password-policy")
        
        assert response.status_code == 200
        data = response.json()
        assert "min_length" in data
        assert "max_length" in data
        assert "requirements" in data
        assert "restrictions" in data
        assert isinstance(data["min_length"], int)
        assert isinstance(data["max_length"], int)
        assert isinstance(data["requirements"], dict)
        assert isinstance(data["restrictions"], dict)


class TestSessionCleanupEndpoint:
    """Test POST /auth/cleanup-sessions endpoint"""
    
    def test_cleanup_sessions(self, test_db, logged_in_user):
        """Test session cleanup endpoint"""
        response = client.post("/auth/cleanup-sessions")
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Cleaned up" in data["message"]
        assert "expired sessions" in data["message"]


class TestUserProfileEndpoints:
    """Test user profile management endpoints"""
    
    def test_get_profile_success(self, test_db, test_user_data, logged_in_user):
        """Test GET /users/profile success"""
        headers = {"Authorization": f"Bearer {logged_in_user['access_token']}"}
        response = client.get("/users/profile", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == test_user_data["username"]
        assert data["email"] == test_user_data["email"]
        assert data["is_active"] is True
        assert data["email_verified"] is False
        assert "created_at" in data
        assert "updated_at" in data
        assert "last_login" in data
    
    def test_get_profile_unauthorized(self, test_db):
        """Test GET /users/profile without token"""
        response = client.get("/users/profile")
        
        assert response.status_code == 401
        assert "Not authenticated" in response.json()["detail"]
    
    def test_get_profile_invalid_token(self, test_db):
        """Test GET /users/profile with invalid token"""
        headers = {"Authorization": "Bearer invalid-token"}
        response = client.get("/users/profile", headers=headers)
        
        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["detail"]
    
    def test_update_profile_success(self, test_db, test_user_data, logged_in_user):
        """Test PATCH /users/profile success"""
        headers = {"Authorization": f"Bearer {logged_in_user['access_token']}"}
        update_data = {"email": "updated@example.com"}
        
        response = client.patch("/users/profile", json=update_data, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "updated@example.com"
        assert data["email_verified"] is False  # Should be reset when email changes
        assert "updated_at" in data
    
    def test_update_profile_username(self, test_db, test_user_data, logged_in_user):
        """Test updating username"""
        headers = {"Authorization": f"Bearer {logged_in_user['access_token']}"}
        update_data = {"username": "newusername"}
        
        response = client.patch("/users/profile", json=update_data, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "newusername"
    
    def test_update_profile_duplicate_username(self, test_db, test_user_data, logged_in_user):
        """Test updating to duplicate username"""
        # Create another user
        other_user_data = {
            "username": "otheruser",
            "email": "other@example.com",
            "password": "SecurePassword123!"
        }
        client.post("/users/", json=other_user_data)
        
        # Try to update to existing username
        headers = {"Authorization": f"Bearer {logged_in_user['access_token']}"}
        update_data = {"username": "otheruser"}
        
        response = client.patch("/users/profile", json=update_data, headers=headers)
        
        assert response.status_code == 400
        assert "Username already taken" in response.json()["detail"]
    
    def test_update_profile_duplicate_email(self, test_db, test_user_data, logged_in_user):
        """Test updating to duplicate email"""
        # Create another user
        other_user_data = {
            "username": "otheruser",
            "email": "other@example.com",
            "password": "SecurePassword123!"
        }
        client.post("/users/", json=other_user_data)
        
        # Try to update to existing email
        headers = {"Authorization": f"Bearer {logged_in_user['access_token']}"}
        update_data = {"email": "other@example.com"}
        
        response = client.patch("/users/profile", json=update_data, headers=headers)
        
        assert response.status_code == 400
        assert "Email already taken" in response.json()["detail"]
    
    def test_update_profile_invalid_email(self, test_db, logged_in_user):
        """Test updating with invalid email format"""
        headers = {"Authorization": f"Bearer {logged_in_user['access_token']}"}
        update_data = {"email": "invalid-email"}
        
        response = client.patch("/users/profile", json=update_data, headers=headers)
        
        assert response.status_code == 400
        assert "Invalid email format" in response.json()["detail"]
    
    def test_update_profile_empty_fields(self, test_db, logged_in_user):
        """Test updating with empty fields"""
        headers = {"Authorization": f"Bearer {logged_in_user['access_token']}"}
        
        # Empty username
        response = client.patch("/users/profile", json={"username": ""}, headers=headers)
        assert response.status_code == 400
        assert "Username cannot be empty" in response.json()["detail"]
        
        # Empty email
        response = client.patch("/users/profile", json={"email": ""}, headers=headers)
        assert response.status_code == 400
        assert "Email cannot be empty" in response.json()["detail"]
    
    def test_update_profile_unauthorized(self, test_db):
        """Test PATCH /users/profile without token"""
        response = client.patch("/users/profile", json={"email": "updated@example.com"})
        
        assert response.status_code == 401
        assert "Not authenticated" in response.json()["detail"]


class TestCurrentUserEndpoint:
    """Test GET /users/me/ endpoint"""
    
    def test_get_current_user_success(self, test_db, test_user_data, logged_in_user):
        """Test GET /users/me/ success"""
        headers = {"Authorization": f"Bearer {logged_in_user['access_token']}"}
        response = client.get("/users/me/", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == test_user_data["username"]
        assert data["email"] == test_user_data["email"]
        assert "id" in data
        assert "hashed_password" not in data  # Should not expose password
    
    def test_get_current_user_unauthorized(self, test_db):
        """Test GET /users/me/ without token"""
        response = client.get("/users/me/")
        
        assert response.status_code == 401
        assert "Not authenticated" in response.json()["detail"]


class TestEndToEndAuthFlow:
    """Test complete end-to-end authentication flows"""
    
    def test_complete_auth_lifecycle(self, test_db, test_user_data):
        """Test complete authentication lifecycle"""
        # 1. Register user
        register_response = client.post("/users/", json=test_user_data)
        assert register_response.status_code == 200
        
        # 2. Login user
        login_response = client.post("/token", data={
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        })
        assert login_response.status_code == 200
        tokens = login_response.json()
        
        # 3. Access protected endpoint
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        profile_response = client.get("/users/profile", headers=headers)
        assert profile_response.status_code == 200
        
        # 4. Refresh tokens
        refresh_response = client.post("/auth/refresh", json={
            "refresh_token": tokens["refresh_token"]
        })
        assert refresh_response.status_code == 200
        new_tokens = refresh_response.json()
        
        # 5. Use new access token
        new_headers = {"Authorization": f"Bearer {new_tokens['access_token']}"}
        profile_response2 = client.get("/users/profile", headers=new_headers)
        assert profile_response2.status_code == 200
        
        # 6. Logout
        logout_response = client.post("/auth/logout", json={
            "refresh_token": new_tokens["refresh_token"]
        })
        assert logout_response.status_code == 200
        
        # 7. Verify tokens are invalidated
        refresh_response2 = client.post("/auth/refresh", json={
            "refresh_token": new_tokens["refresh_token"]
        })
        assert refresh_response2.status_code == 401


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"]) 