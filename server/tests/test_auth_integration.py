#!/usr/bin/env python3
"""
Integration Tests for Complete Authentication Flow
Task 5.7: Create integration tests for complete authentication flow

This test suite tests the entire authentication system end-to-end,
including API endpoints, database interactions, token management,
and complete user workflows.
"""

import pytest
import sys
import os
import json
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel, select

# Add the server directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from models import User, UserSession, PasswordResetToken
from auth import get_password_hash, verify_password
from database import get_session

# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_auth_integration.db"
test_engine = create_engine(TEST_DATABASE_URL, echo=False, connect_args={"check_same_thread": False})

def get_test_session():
    """Get test database session"""
    with Session(test_engine) as session:
        yield session

# Override the dependency
app.dependency_overrides[get_session] = get_test_session

# Create test client
client = TestClient(app)

@pytest.fixture(scope="function")
def test_db():
    """Create test database for each test"""
    SQLModel.metadata.create_all(test_engine)
    yield
    SQLModel.metadata.drop_all(test_engine)
    # Clean up test database file
    import os
    if os.path.exists("./test_auth_integration.db"):
        os.remove("./test_auth_integration.db")

@pytest.fixture
def test_user_data():
    """Test user data for registration"""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "SecurePassword123!"
    }

@pytest.fixture
def test_session():
    """Get test database session"""
    with Session(test_engine) as session:
        yield session


class TestUserRegistrationFlow:
    """Integration tests for user registration flow"""
    
    def test_complete_registration_flow(self, test_db, test_user_data):
        """Test complete user registration flow"""
        # Test user registration
        response = client.post("/auth/register", json=test_user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == test_user_data["username"]
        assert data["user"]["email"] == test_user_data["email"]
        assert data["user"]["is_active"] is True
        
        # Verify user was created in database
        with Session(test_engine) as session:
            user = session.exec(select(User).where(User.username == test_user_data["username"])).first()
            assert user is not None
            assert user.email == test_user_data["email"]
            assert verify_password(test_user_data["password"], user.hashed_password)
    
    def test_registration_duplicate_username(self, test_db, test_user_data):
        """Test registration with duplicate username"""
        # Register first user
        client.post("/auth/register", json=test_user_data)
        
        # Try to register with same username
        duplicate_data = test_user_data.copy()
        duplicate_data["email"] = "different@example.com"
        
        response = client.post("/auth/register", json=duplicate_data)
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]
    
    def test_registration_duplicate_email(self, test_db, test_user_data):
        """Test registration with duplicate email"""
        # Register first user
        client.post("/auth/register", json=test_user_data)
        
        # Try to register with same email
        duplicate_data = test_user_data.copy()
        duplicate_data["username"] = "differentuser"
        
        response = client.post("/auth/register", json=duplicate_data)
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]
    
    def test_registration_invalid_password(self, test_db, test_user_data):
        """Test registration with invalid password"""
        invalid_data = test_user_data.copy()
        invalid_data["password"] = "weak"
        
        response = client.post("/auth/register", json=invalid_data)
        assert response.status_code == 400
        # Should fail due to password validation


class TestUserLoginFlow:
    """Integration tests for user login flow"""
    
    def test_complete_login_flow(self, test_db, test_user_data):
        """Test complete user login flow"""
        # First register a user
        client.post("/auth/register", json=test_user_data)
        
        # Test login
        login_data = {
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        }
        
        response = client.post("/auth/login", data=login_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        
        # Verify refresh token was stored in database
        with Session(test_engine) as session:
            user = session.exec(select(User).where(User.username == test_user_data["username"])).first()
            user_session = session.exec(select(UserSession).where(UserSession.user_id == user.id)).first()
            assert user_session is not None
            assert user_session.refresh_token == data["refresh_token"]
            assert user_session.is_active is True
    
    def test_login_invalid_credentials(self, test_db, test_user_data):
        """Test login with invalid credentials"""
        # Register user
        client.post("/auth/register", json=test_user_data)
        
        # Test login with wrong password
        login_data = {
            "username": test_user_data["username"],
            "password": "wrongpassword"
        }
        
        response = client.post("/auth/login", data=login_data)
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]
    
    def test_login_nonexistent_user(self, test_db):
        """Test login with non-existent user"""
        login_data = {
            "username": "nonexistent",
            "password": "password"
        }
        
        response = client.post("/auth/login", data=login_data)
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]
    
    def test_login_account_lockout(self, test_db, test_user_data):
        """Test account lockout after failed login attempts"""
        # Register user
        client.post("/auth/register", json=test_user_data)
        
        # Make multiple failed login attempts
        login_data = {
            "username": test_user_data["username"],
            "password": "wrongpassword"
        }
        
        # Make 5+ failed attempts to trigger lockout
        for _ in range(6):
            response = client.post("/auth/login", data=login_data)
            assert response.status_code == 401
        
        # Verify account is locked in database
        with Session(test_engine) as session:
            user = session.exec(select(User).where(User.username == test_user_data["username"])).first()
            assert user.failed_login_attempts >= 5
            assert user.locked_until is not None
            assert user.locked_until > datetime.utcnow()
        
        # Try to login with correct credentials should fail due to lockout
        correct_login_data = {
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        }
        
        response = client.post("/auth/login", data=correct_login_data)
        assert response.status_code == 401
        assert "Account temporarily locked" in response.json()["detail"]


class TestTokenManagementFlow:
    """Integration tests for token management flow"""
    
    def test_access_protected_endpoint(self, test_db, test_user_data):
        """Test accessing protected endpoint with valid token"""
        # Register and login
        client.post("/auth/register", json=test_user_data)
        login_response = client.post("/auth/login", data={
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        })
        
        access_token = login_response.json()["access_token"]
        
        # Access protected endpoint
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.get("/users/profile", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == test_user_data["username"]
        assert data["email"] == test_user_data["email"]
    
    def test_access_protected_endpoint_invalid_token(self, test_db):
        """Test accessing protected endpoint with invalid token"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/users/profile", headers=headers)
        
        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["detail"]
    
    def test_access_protected_endpoint_no_token(self, test_db):
        """Test accessing protected endpoint without token"""
        response = client.get("/users/profile")
        
        assert response.status_code == 401
        assert "Not authenticated" in response.json()["detail"]
    
    def test_refresh_token_flow(self, test_db, test_user_data):
        """Test token refresh flow"""
        # Register and login
        client.post("/auth/register", json=test_user_data)
        login_response = client.post("/auth/login", data={
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        })
        
        refresh_token = login_response.json()["refresh_token"]
        
        # Use refresh token to get new access token
        refresh_data = {"refresh_token": refresh_token}
        response = client.post("/auth/refresh", json=refresh_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        
        # Verify new access token works
        new_access_token = data["access_token"]
        headers = {"Authorization": f"Bearer {new_access_token}"}
        profile_response = client.get("/users/profile", headers=headers)
        assert profile_response.status_code == 200
    
    def test_refresh_token_invalid(self, test_db):
        """Test refresh with invalid token"""
        refresh_data = {"refresh_token": "invalid_token"}
        response = client.post("/auth/refresh", json=refresh_data)
        
        assert response.status_code == 401
        assert "Invalid refresh token" in response.json()["detail"]
    
    def test_logout_flow(self, test_db, test_user_data):
        """Test complete logout flow"""
        # Register and login
        client.post("/auth/register", json=test_user_data)
        login_response = client.post("/auth/login", data={
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        })
        
        access_token = login_response.json()["access_token"]
        refresh_token = login_response.json()["refresh_token"]
        
        # Logout
        headers = {"Authorization": f"Bearer {access_token}"}
        logout_data = {"refresh_token": refresh_token}
        response = client.post("/auth/logout", json=logout_data, headers=headers)
        
        assert response.status_code == 200
        assert response.json()["message"] == "Successfully logged out"
        
        # Verify refresh token is blacklisted
        with Session(test_engine) as session:
            user_session = session.exec(
                select(UserSession).where(UserSession.refresh_token == refresh_token)
            ).first()
            assert user_session.is_active is False
        
        # Try to use blacklisted refresh token
        refresh_response = client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert refresh_response.status_code == 401


class TestPasswordResetFlow:
    """Integration tests for password reset flow"""
    
    def test_request_password_reset(self, test_db, test_user_data):
        """Test password reset request"""
        # Register user
        client.post("/auth/register", json=test_user_data)
        
        # Request password reset
        reset_data = {"email": test_user_data["email"]}
        response = client.post("/auth/request-password-reset", json=reset_data)
        
        assert response.status_code == 200
        assert "password reset email sent" in response.json()["message"].lower()
        
        # Verify reset token was created in database
        with Session(test_engine) as session:
            user = session.exec(select(User).where(User.email == test_user_data["email"])).first()
            reset_token = session.exec(
                select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
            ).first()
            assert reset_token is not None
            assert reset_token.is_used is False
            assert reset_token.expires_at > datetime.utcnow()
    
    def test_reset_password_with_valid_token(self, test_db, test_user_data):
        """Test password reset with valid token"""
        # Register user and request password reset
        client.post("/auth/register", json=test_user_data)
        client.post("/auth/request-password-reset", json={"email": test_user_data["email"]})
        
        # Get the reset token from database
        with Session(test_engine) as session:
            user = session.exec(select(User).where(User.email == test_user_data["email"])).first()
            reset_token = session.exec(
                select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
            ).first()
            token_string = reset_token.token
        
        # Reset password
        new_password = "NewSecurePassword123!"
        reset_data = {
            "token": token_string,
            "new_password": new_password
        }
        response = client.post("/auth/reset-password", json=reset_data)
        
        assert response.status_code == 200
        assert "password has been reset" in response.json()["message"].lower()
        
        # Verify password was changed and token was marked as used
        with Session(test_engine) as session:
            user = session.exec(select(User).where(User.email == test_user_data["email"])).first()
            assert verify_password(new_password, user.hashed_password)
            
            reset_token = session.exec(
                select(PasswordResetToken).where(PasswordResetToken.token == token_string)
            ).first()
            assert reset_token.is_used is True
        
        # Verify can login with new password
        login_response = client.post("/auth/login", data={
            "username": test_user_data["username"],
            "password": new_password
        })
        assert login_response.status_code == 200
    
    def test_reset_password_with_invalid_token(self, test_db):
        """Test password reset with invalid token"""
        reset_data = {
            "token": "invalid_token",
            "new_password": "NewPassword123!"
        }
        response = client.post("/auth/reset-password", json=reset_data)
        
        assert response.status_code == 400
        assert "Invalid or expired reset token" in response.json()["detail"]
    
    def test_password_reset_request_nonexistent_email(self, test_db):
        """Test password reset request with non-existent email"""
        reset_data = {"email": "nonexistent@example.com"}
        response = client.post("/auth/request-password-reset", json=reset_data)
        
        # Should still return success for security reasons
        assert response.status_code == 200
        assert "password reset email sent" in response.json()["message"].lower()


class TestCompleteUserJourney:
    """Integration tests for complete user journey scenarios"""
    
    def test_complete_user_lifecycle(self, test_db, test_user_data):
        """Test complete user lifecycle from registration to profile management"""
        # 1. Register user
        register_response = client.post("/auth/register", json=test_user_data)
        assert register_response.status_code == 201
        
        # 2. Login
        login_response = client.post("/auth/login", data={
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        })
        assert login_response.status_code == 200
        access_token = login_response.json()["access_token"]
        
        # 3. Access profile
        headers = {"Authorization": f"Bearer {access_token}"}
        profile_response = client.get("/users/profile", headers=headers)
        assert profile_response.status_code == 200
        
        # 4. Update profile
        update_data = {"email": "updated@example.com"}
        update_response = client.patch("/users/profile", json=update_data, headers=headers)
        assert update_response.status_code == 200
        
        # 5. Verify update
        updated_profile = client.get("/users/profile", headers=headers)
        assert updated_profile.json()["email"] == "updated@example.com"
        
        # 6. Logout
        refresh_token = login_response.json()["refresh_token"]
        logout_response = client.post("/auth/logout", 
                                    json={"refresh_token": refresh_token}, 
                                    headers=headers)
        assert logout_response.status_code == 200
    
    def test_multiple_sessions_management(self, test_db, test_user_data):
        """Test multiple user sessions and session management"""
        # Register user
        client.post("/auth/register", json=test_user_data)
        
        login_data = {
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        }
        
        # Create multiple sessions
        session1 = client.post("/auth/login", data=login_data)
        session2 = client.post("/auth/login", data=login_data)
        session3 = client.post("/auth/login", data=login_data)
        
        assert session1.status_code == 200
        assert session2.status_code == 200
        assert session3.status_code == 200
        
        # Verify all sessions are stored in database
        with Session(test_engine) as session:
            user = session.exec(select(User).where(User.username == test_user_data["username"])).first()
            user_sessions = session.exec(
                select(UserSession).where(UserSession.user_id == user.id, UserSession.is_active == True)
            ).all()
            assert len(user_sessions) == 3
        
        # Logout from one session
        token1 = session1.json()["refresh_token"]
        headers = {"Authorization": f"Bearer {session1.json()['access_token']}"}
        logout_response = client.post("/auth/logout", 
                                    json={"refresh_token": token1}, 
                                    headers=headers)
        assert logout_response.status_code == 200
        
        # Verify only one session was deactivated
        with Session(test_engine) as session:
            active_sessions = session.exec(
                select(UserSession).where(UserSession.user_id == user.id, UserSession.is_active == True)
            ).all()
            assert len(active_sessions) == 2
    
    def test_concurrent_user_operations(self, test_db):
        """Test concurrent operations with multiple users"""
        # Create multiple users
        users_data = [
            {"username": "user1", "email": "user1@example.com", "password": "Password123!"},
            {"username": "user2", "email": "user2@example.com", "password": "Password123!"},
            {"username": "user3", "email": "user3@example.com", "password": "Password123!"}
        ]
        
        # Register all users
        for user_data in users_data:
            response = client.post("/auth/register", json=user_data)
            assert response.status_code == 201
        
        # Login all users
        tokens = []
        for user_data in users_data:
            login_response = client.post("/auth/login", data={
                "username": user_data["username"],
                "password": user_data["password"]
            })
            assert login_response.status_code == 200
            tokens.append(login_response.json()["access_token"])
        
        # All users access their profiles simultaneously
        for i, token in enumerate(tokens):
            headers = {"Authorization": f"Bearer {token}"}
            response = client.get("/users/profile", headers=headers)
            assert response.status_code == 200
            assert response.json()["username"] == users_data[i]["username"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 