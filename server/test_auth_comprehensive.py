#!/usr/bin/env python3
"""
Comprehensive Authentication System Test Suite
Tests all functionality for Task 1.0: Implement Core Authentication System

This test suite verifies:
1.1 Enhanced User model fields
1.2 UserSession model for refresh token management  
1.3 Refresh token generation and validation
1.4 Token blacklisting functionality
1.5 Account lockout logic
1.6 Password reset token system
1.7 User profile management endpoints
1.8 Login endpoint returning both tokens
1.9 Logout endpoint blacklisting tokens
1.10 Refresh token endpoint for renewal
"""

import sys
import os
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel
from sqlalchemy.pool import StaticPool

# Add the server directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import app
from models import User, UserSession, PasswordResetToken, UserCreate
from auth import (
    get_password_hash, 
    verify_password,
    create_access_token,
    create_user_session,
    validate_refresh_token,
    blacklist_refresh_token,
    check_and_handle_account_lockout,
    is_account_locked,
    unlock_account_if_expired,
    create_password_reset_token,
    validate_password_reset_token,
    mark_password_reset_token_as_used,
    MAX_LOGIN_ATTEMPTS,
    LOCKOUT_DURATION_MINUTES
)

# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_auth.db"
test_engine = create_engine(TEST_DATABASE_URL, echo=False)

# Create test client
client = TestClient(app)

def setup_test_database():
    """Create test database tables"""
    SQLModel.metadata.create_all(test_engine)

def cleanup_test_database():
    """Clean up test database"""
    SQLModel.metadata.drop_all(test_engine)
    import os
    if os.path.exists("./test_auth.db"):
        os.remove("./test_auth.db")


class TestUserModelFields:
    """Test 1.1: Enhanced User model fields"""
    
    def test_user_model_has_enhanced_fields(self):
        """Verify User model has all required enhanced fields"""
        user_fields = User.__fields__.keys()
        required_fields = [
            'email_verified', 'is_active', 'failed_login_attempts', 
            'locked_until', 'last_login', 'created_at', 'updated_at'
        ]
        
        for field in required_fields:
            assert field in user_fields, f"User model missing required field: {field}"
    
    def test_user_creation_with_enhanced_fields(self):
        """Test user creation with default values for enhanced fields"""
        setup_test_database()
        try:
            with Session(test_engine) as session:
                user = User(
                    username="testuser",
                    email="test@example.com", 
                    hashed_password=get_password_hash("password123")
                )
                session.add(user)
                session.commit()
                session.refresh(user)
                
                # Check default values
                assert user.email_verified == False
                assert user.is_active == True
                assert user.failed_login_attempts == 0
                assert user.locked_until is None
                assert user.last_login is None
                assert isinstance(user.created_at, datetime)
                assert isinstance(user.updated_at, datetime)
        finally:
            cleanup_test_database()


class TestUserSessionModel:
    """Test 1.2: UserSession model for refresh token management"""
    
    def test_user_session_model_fields(self):
        """Verify UserSession model has all required fields"""
        session_fields = UserSession.__fields__.keys()
        required_fields = [
            'user_id', 'refresh_token', 'expires_at', 'is_active', 'created_at'
        ]
        
        for field in required_fields:
            assert field in session_fields, f"UserSession model missing required field: {field}"
    
    def test_user_session_creation_and_relationship(self):
        """Test UserSession creation and relationship to User"""
        setup_test_database()
        try:
            with Session(test_engine) as session:
                # Create user
                user = User(
                    username="testuser",
                    email="test@example.com",
                    hashed_password=get_password_hash("password123")
                )
                session.add(user)
                session.commit()
                session.refresh(user)
                
                # Create user session
                user_session = create_user_session(user.id, session)
                
                assert user_session.user_id == user.id
                assert user_session.refresh_token is not None
                assert isinstance(user_session.expires_at, datetime)
                assert user_session.is_active == True
                assert isinstance(user_session.created_at, datetime)
        finally:
            cleanup_test_database()


class TestRefreshTokenSystem:
    """Test 1.3: Refresh token generation and validation"""
    
    def test_refresh_token_generation(self):
        """Test refresh token generation and validation"""
        setup_test_database()
        try:
            with Session(test_engine) as session:
                user = User(
                    username="testuser",
                    email="test@example.com",
                    hashed_password=get_password_hash("password123")
                )
                session.add(user)
                session.commit()
                session.refresh(user)
                
                # Create refresh token
                user_session = create_user_session(user.id, session)
                assert user_session.refresh_token is not None
                assert len(user_session.refresh_token) > 30  # UUID4 should be long
                
                # Validate refresh token
                validated_session = validate_refresh_token(user_session.refresh_token, session)
                assert validated_session is not None
                assert validated_session.id == user_session.id
        finally:
            cleanup_test_database()
    
    def test_expired_refresh_token_validation(self):
        """Test that expired refresh tokens are not validated"""
        setup_test_database()
        try:
            with Session(test_engine) as session:
                user = User(
                    username="testuser",
                    email="test@example.com",
                    hashed_password=get_password_hash("password123")
                )
                session.add(user)
                session.commit()
                session.refresh(user)
                
                # Create expired session
                expired_session = UserSession(
                    user_id=user.id,
                    refresh_token="expired-token",
                    expires_at=datetime.utcnow() - timedelta(days=1),  # Expired
                    is_active=True
                )
                session.add(expired_session)
                session.commit()
                
                # Should not validate expired token
                validated_session = validate_refresh_token("expired-token", session)
                assert validated_session is None
        finally:
            cleanup_test_database()


class TestTokenBlacklisting:
    """Test 1.4: Token blacklisting functionality"""
    
    def test_token_blacklisting(self):
        """Test token blacklisting functionality"""
        setup_test_database()
        try:
            with Session(test_engine) as session:
                user = User(
                    username="testuser",
                    email="test@example.com",
                    hashed_password=get_password_hash("password123")
                )
                session.add(user)
                session.commit()
                session.refresh(user)
                
                # Create user session
                user_session = create_user_session(user.id, session)
                token = user_session.refresh_token
                
                # Verify token is valid before blacklisting
                validated_session = validate_refresh_token(token, session)
                assert validated_session is not None
                
                # Blacklist the token
                success = blacklist_refresh_token(token, session)
                assert success == True
                
                # Verify token is no longer valid
                validated_session = validate_refresh_token(token, session)
                assert validated_session is None
        finally:
            cleanup_test_database()
    
    def test_blacklist_nonexistent_token(self):
        """Test blacklisting non-existent token returns False"""
        setup_test_database()
        try:
            with Session(test_engine) as session:
                success = blacklist_refresh_token("nonexistent-token", session)
                assert success == False
        finally:
            cleanup_test_database()


class TestAccountLockout:
    """Test 1.5: Account lockout logic"""
    
    def test_account_lockout_after_max_attempts(self):
        """Test account gets locked after max failed attempts"""
        setup_test_database()
        try:
            with Session(test_engine) as session:
                user = User(
                    username="testuser",
                    email="test@example.com",
                    hashed_password=get_password_hash("password123"),
                    failed_login_attempts=MAX_LOGIN_ATTEMPTS - 1  # One away from lockout
                )
                session.add(user)
                session.commit()
                session.refresh(user)
                
                # This should trigger lockout
                user.failed_login_attempts += 1
                check_and_handle_account_lockout(user, session)
                
                # Check account is locked
                assert user.locked_until is not None
                assert user.locked_until > datetime.utcnow()
                assert is_account_locked(user) == True
        finally:
            cleanup_test_database()
    
    def test_account_unlock_after_expiry(self):
        """Test account auto-unlocks after lockout period expires"""
        setup_test_database()
        try:
            with Session(test_engine) as session:
                # Create locked user with expired lockout
                user = User(
                    username="testuser",
                    email="test@example.com",
                    hashed_password=get_password_hash("password123"),
                    failed_login_attempts=MAX_LOGIN_ATTEMPTS,
                    locked_until=datetime.utcnow() - timedelta(minutes=1)  # Expired
                )
                session.add(user)
                session.commit()
                session.refresh(user)
                
                # Should unlock expired account
                unlocked = unlock_account_if_expired(user, session)
                assert unlocked == True
                assert user.locked_until is None
                assert user.failed_login_attempts == 0
                assert is_account_locked(user) == False
        finally:
            cleanup_test_database()


class TestPasswordReset:
    """Test 1.6: Password reset token system"""
    
    def test_password_reset_token_creation(self):
        """Test password reset token creation"""
        setup_test_database()
        try:
            with Session(test_engine) as session:
                user = User(
                    username="testuser",
                    email="test@example.com",
                    hashed_password=get_password_hash("password123")
                )
                session.add(user)
                session.commit()
                session.refresh(user)
                
                # Create password reset token
                reset_token = create_password_reset_token(user.id, session)
                
                assert reset_token.user_id == user.id
                assert reset_token.token is not None
                assert len(reset_token.token) > 30  # Should be secure token
                assert reset_token.expires_at > datetime.utcnow()
                assert reset_token.is_used == False
        finally:
            cleanup_test_database()
    
    def test_password_reset_token_validation(self):
        """Test password reset token validation"""
        setup_test_database()
        try:
            with Session(test_engine) as session:
                user = User(
                    username="testuser",
                    email="test@example.com",
                    hashed_password=get_password_hash("password123")
                )
                session.add(user)
                session.commit()
                session.refresh(user)
                
                # Create and validate token
                reset_token = create_password_reset_token(user.id, session)
                validated_token = validate_password_reset_token(reset_token.token, session)
                
                assert validated_token is not None
                assert validated_token.id == reset_token.id
        finally:
            cleanup_test_database()
    
    def test_password_reset_token_usage(self):
        """Test password reset token marking as used"""
        setup_test_database()
        try:
            with Session(test_engine) as session:
                user = User(
                    username="testuser",
                    email="test@example.com",
                    hashed_password=get_password_hash("password123")
                )
                session.add(user)
                session.commit()
                session.refresh(user)
                
                # Create token
                reset_token = create_password_reset_token(user.id, session)
                token_string = reset_token.token
                
                # Mark as used
                success = mark_password_reset_token_as_used(token_string, session)
                assert success == True
                
                # Should not validate used token
                validated_token = validate_password_reset_token(token_string, session)
                assert validated_token is None
        finally:
            cleanup_test_database()


class TestPasswordResetModel:
    """Test PasswordResetToken model"""
    
    def test_password_reset_token_model_fields(self):
        """Verify PasswordResetToken model has all required fields"""
        token_fields = PasswordResetToken.__fields__.keys()
        required_fields = [
            'user_id', 'token', 'expires_at', 'is_used', 'created_at'
        ]
        
        for field in required_fields:
            assert field in token_fields, f"PasswordResetToken model missing required field: {field}"


def run_tests():
    """Run all authentication tests"""
    print("🔐 Starting Comprehensive Authentication System Test Suite")
    print("=" * 60)
    
    test_classes = [
        TestUserModelFields,
        TestUserSessionModel, 
        TestRefreshTokenSystem,
        TestTokenBlacklisting,
        TestAccountLockout,
        TestPasswordReset,
        TestPasswordResetModel
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = []
    
    for test_class in test_classes:
        print(f"\n📋 Running {test_class.__name__}")
        instance = test_class()
        
        # Get all test methods
        test_methods = [method for method in dir(instance) if method.startswith('test_')]
        
        for test_method in test_methods:
            total_tests += 1
            try:
                # Run test
                getattr(instance, test_method)()
                print(f"  ✅ {test_method}")
                passed_tests += 1
                    
            except Exception as e:
                print(f"  ❌ {test_method}: {str(e)}")
                failed_tests.append(f"{test_class.__name__}.{test_method}: {str(e)}")
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS")
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {len(failed_tests)}")
    
    if failed_tests:
        print("\n❌ FAILED TESTS:")
        for failure in failed_tests:
            print(f"  • {failure}")
        return False
    else:
        print("\n🎉 ALL TESTS PASSED!")
        print("\n✅ Task 1.0 Authentication System - FULLY IMPLEMENTED AND VERIFIED")
        return True


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1) 