#!/usr/bin/env python3
"""
Unit Tests for Authentication Service Functionality
Task 5.5: Create unit tests for authentication service functionality

This test suite focuses on unit testing individual authentication functions
with proper mocking, edge cases, and isolated testing scenarios.
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi import HTTPException
from sqlmodel import Session

# Add the server directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    create_user_session,
    validate_refresh_token,
    blacklist_refresh_token,
    cleanup_expired_sessions,
    get_current_user,
    check_and_handle_account_lockout,
    is_account_locked,
    unlock_account_if_expired,
    generate_password_reset_token,
    create_password_reset_token,
    validate_password_reset_token,
    mark_password_reset_token_as_used,
    cleanup_expired_password_reset_tokens,
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    MAX_LOGIN_ATTEMPTS,
    LOCKOUT_DURATION_MINUTES
)
from models import User, UserSession, PasswordResetToken


class TestPasswordFunctions:
    """Unit tests for password hashing and verification functions"""
    
    def test_get_password_hash_returns_string(self):
        """Test that password hashing returns a string"""
        password = "test_password_123"
        hashed = get_password_hash(password)
        
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        assert hashed != password  # Should not return plain password
    
    def test_get_password_hash_different_for_same_password(self):
        """Test that same password produces different hashes (salt effect)"""
        password = "same_password"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        assert hash1 != hash2  # Different due to salt
    
    def test_verify_password_correct_password(self):
        """Test password verification with correct password"""
        password = "correct_password"
        hashed = get_password_hash(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect_password(self):
        """Test password verification with incorrect password"""
        password = "correct_password"
        wrong_password = "wrong_password"
        hashed = get_password_hash(password)
        
        assert verify_password(wrong_password, hashed) is False
    
    def test_verify_password_empty_strings(self):
        """Test password verification with empty strings"""
        empty_hash = get_password_hash("")
        assert verify_password("", empty_hash) is True
        assert verify_password("nonempty", empty_hash) is False


class TestTokenFunctions:
    """Unit tests for token creation and management functions"""
    
    def test_create_access_token_default_expiry(self):
        """Test access token creation with default expiry"""
        data = {"sub": "testuser", "user_id": 1}
        token = create_access_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Decode and verify token structure
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert decoded["sub"] == "testuser"
        assert decoded["user_id"] == 1
        assert "exp" in decoded
    
    def test_create_access_token_custom_expiry(self):
        """Test access token creation with custom expiry"""
        data = {"sub": "testuser"}
        custom_expiry = timedelta(minutes=60)
        token = create_access_token(data, custom_expiry)
        
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp_time = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        expected_time = datetime.now(timezone.utc) + custom_expiry
        
        # Allow 5 second tolerance
        assert abs((exp_time - expected_time).total_seconds()) < 5
    
    def test_create_refresh_token_unique(self):
        """Test that refresh tokens are unique"""
        token1 = create_refresh_token()
        token2 = create_refresh_token()
        
        assert isinstance(token1, str)
        assert isinstance(token2, str)
        assert token1 != token2
        assert len(token1) > 30  # UUID4 should be reasonably long
    
    def test_create_access_token_with_empty_data(self):
        """Test access token creation with empty data"""
        token = create_access_token({})
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        assert "exp" in decoded
        assert len(decoded.keys()) == 1  # Only exp should be present


class TestUserSessionFunctions:
    """Unit tests for user session management functions"""
    
    @patch('auth.Session')
    def test_create_user_session(self, mock_session_class):
        """Test user session creation"""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        user_id = 1
        session = create_user_session(user_id, mock_session)
        
        # Verify session object creation
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()
        
        # Check session attributes
        added_session = mock_session.add.call_args[0][0]
        assert isinstance(added_session, UserSession)
        assert added_session.user_id == user_id
        assert len(added_session.refresh_token) > 30
        assert added_session.expires_at > datetime.utcnow()
    
    @patch('auth.select')
    def test_validate_refresh_token_valid(self, mock_select):
        """Test validation of valid refresh token"""
        mock_session = MagicMock()
        mock_user_session = MagicMock()
        mock_user_session.refresh_token = "valid_token"
        mock_user_session.is_active = True
        mock_user_session.expires_at = datetime.utcnow() + timedelta(hours=1)
        
        mock_session.exec.return_value.first.return_value = mock_user_session
        
        result = validate_refresh_token("valid_token", mock_session)
        
        assert result == mock_user_session
        mock_session.exec.assert_called_once()
    
    @patch('auth.select')
    def test_validate_refresh_token_invalid(self, mock_select):
        """Test validation of invalid refresh token"""
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        
        result = validate_refresh_token("invalid_token", mock_session)
        
        assert result is None
        mock_session.exec.assert_called_once()
    
    @patch('auth.select')
    def test_blacklist_refresh_token_success(self, mock_select):
        """Test successful token blacklisting"""
        mock_session = MagicMock()
        mock_user_session = MagicMock()
        mock_user_session.is_active = True
        mock_session.exec.return_value.first.return_value = mock_user_session
        
        result = blacklist_refresh_token("valid_token", mock_session)
        
        assert result is True
        assert mock_user_session.is_active is False
        mock_session.add.assert_called_once_with(mock_user_session)
        mock_session.commit.assert_called_once()
    
    @patch('auth.select')
    def test_blacklist_refresh_token_not_found(self, mock_select):
        """Test blacklisting non-existent token"""
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        
        result = blacklist_refresh_token("nonexistent_token", mock_session)
        
        assert result is False
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()


class TestAccountLockoutFunctions:
    """Unit tests for account lockout functionality"""
    
    def test_is_account_locked_when_locked(self):
        """Test account lockout detection when account is locked"""
        user = Mock()
        user.locked_until = datetime.utcnow() + timedelta(minutes=10)
        
        assert is_account_locked(user) is True
    
    def test_is_account_locked_when_not_locked(self):
        """Test account lockout detection when account is not locked"""
        user = Mock()
        user.locked_until = None
        
        assert is_account_locked(user) is False
    
    def test_is_account_locked_when_lockout_expired(self):
        """Test account lockout detection when lockout has expired"""
        user = Mock()
        user.locked_until = datetime.utcnow() - timedelta(minutes=10)
        
        assert is_account_locked(user) is False
    
    def test_check_and_handle_account_lockout_triggers_lockout(self):
        """Test account lockout when max attempts reached"""
        mock_session = MagicMock()
        user = Mock()
        user.failed_login_attempts = MAX_LOGIN_ATTEMPTS
        user.username = "testuser"
        
        check_and_handle_account_lockout(user, mock_session)
        
        assert user.locked_until is not None
        assert user.locked_until > datetime.utcnow()
        assert user.updated_at is not None
        mock_session.add.assert_called_once_with(user)
        mock_session.commit.assert_called_once()
    
    def test_check_and_handle_account_lockout_no_lockout(self):
        """Test no lockout when under max attempts"""
        mock_session = MagicMock()
        user = Mock()
        user.failed_login_attempts = MAX_LOGIN_ATTEMPTS - 1
        
        original_locked_until = user.locked_until
        check_and_handle_account_lockout(user, mock_session)
        
        assert user.locked_until == original_locked_until
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()
    
    def test_unlock_account_if_expired_unlocks_account(self):
        """Test account unlocking when lockout has expired"""
        mock_session = MagicMock()
        user = Mock()
        user.locked_until = datetime.utcnow() - timedelta(minutes=10)
        user.failed_login_attempts = 5
        user.username = "testuser"
        
        result = unlock_account_if_expired(user, mock_session)
        
        assert result is True
        assert user.locked_until is None
        assert user.failed_login_attempts == 0
        assert user.updated_at is not None
        mock_session.add.assert_called_once_with(user)
        mock_session.commit.assert_called_once()
    
    def test_unlock_account_if_expired_no_unlock_needed(self):
        """Test no unlocking when account is not locked"""
        mock_session = MagicMock()
        user = Mock()
        user.locked_until = None
        
        result = unlock_account_if_expired(user, mock_session)
        
        assert result is False
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()


class TestPasswordResetFunctions:
    """Unit tests for password reset functionality"""
    
    def test_generate_password_reset_token(self):
        """Test password reset token generation"""
        token = generate_password_reset_token()
        
        assert isinstance(token, str)
        assert len(token) > 30  # Should be secure and reasonably long
    
    def test_generate_password_reset_token_unique(self):
        """Test that password reset tokens are unique"""
        token1 = generate_password_reset_token()
        token2 = generate_password_reset_token()
        
        assert token1 != token2
    
    @patch('auth.select')
    def test_create_password_reset_token_invalidates_existing(self, mock_select):
        """Test that creating new token invalidates existing ones"""
        mock_session = MagicMock()
        existing_token = Mock()
        existing_token.is_used = False
        mock_session.exec.return_value.all.return_value = [existing_token]
        
        user_id = 1
        result = create_password_reset_token(user_id, mock_session)
        
        # Check existing token was invalidated
        assert existing_token.is_used is True
        mock_session.add.assert_called()
        mock_session.commit.assert_called()
        mock_session.refresh.assert_called()
    
    @patch('auth.select')
    def test_validate_password_reset_token_valid(self, mock_select):
        """Test validation of valid password reset token"""
        mock_session = MagicMock()
        mock_token = Mock()
        mock_token.token = "valid_reset_token"
        mock_token.is_used = False
        mock_token.expires_at = datetime.utcnow() + timedelta(hours=1)
        
        mock_session.exec.return_value.first.return_value = mock_token
        
        result = validate_password_reset_token("valid_reset_token", mock_session)
        
        assert result == mock_token
        mock_session.exec.assert_called_once()
    
    @patch('auth.select')
    def test_validate_password_reset_token_invalid(self, mock_select):
        """Test validation of invalid password reset token"""
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        
        result = validate_password_reset_token("invalid_token", mock_session)
        
        assert result is None
        mock_session.exec.assert_called_once()
    
    @patch('auth.select')
    def test_mark_password_reset_token_as_used_success(self, mock_select):
        """Test marking password reset token as used"""
        mock_session = MagicMock()
        mock_token = Mock()
        mock_token.is_used = False
        mock_session.exec.return_value.first.return_value = mock_token
        
        result = mark_password_reset_token_as_used("valid_token", mock_session)
        
        assert result is True
        assert mock_token.is_used is True
        mock_session.add.assert_called_once_with(mock_token)
        mock_session.commit.assert_called_once()
    
    @patch('auth.select')
    def test_mark_password_reset_token_as_used_not_found(self, mock_select):
        """Test marking non-existent token as used"""
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None
        
        result = mark_password_reset_token_as_used("nonexistent_token", mock_session)
        
        assert result is False
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()


class TestGetCurrentUser:
    """Unit tests for get_current_user function"""
    
    @patch('auth.Session')
    @patch('auth.select')
    @patch('auth.unlock_account_if_expired')
    @patch('auth.is_account_locked')
    def test_get_current_user_valid_token(self, mock_is_locked, mock_unlock, mock_select, mock_session_class):
        """Test getting current user with valid token"""
        # Mock JWT decode
        with patch('auth.jwt.decode') as mock_decode:
            mock_decode.return_value = {"sub": "testuser"}
            
            # Mock database session
            mock_session = MagicMock()
            mock_session_class.return_value.__enter__.return_value = mock_session
            
            # Mock user
            mock_user = Mock()
            mock_user.username = "testuser"
            mock_user.is_active = True
            mock_session.exec.return_value.first.return_value = mock_user
            
            # Mock account status
            mock_is_locked.return_value = False
            
            result = get_current_user("valid_token")
            
            assert result == mock_user
            mock_unlock.assert_called_once()
            mock_is_locked.assert_called_once()
    
    @patch('auth.jwt.decode')
    def test_get_current_user_invalid_token(self, mock_decode):
        """Test getting current user with invalid token"""
        mock_decode.side_effect = JWTError("Invalid token")
        
        with pytest.raises(HTTPException) as exc_info:
            get_current_user("invalid_token")
        
        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in str(exc_info.value.detail)
    
    @patch('auth.Session')
    @patch('auth.select')
    @patch('auth.jwt.decode')
    def test_get_current_user_inactive_user(self, mock_decode, mock_select, mock_session_class):
        """Test getting current user when user is inactive"""
        mock_decode.return_value = {"sub": "testuser"}
        
        # Mock database session
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = mock_session
        
        # Mock inactive user
        mock_user = Mock()
        mock_user.is_active = False
        mock_session.exec.return_value.first.return_value = mock_user
        
        with pytest.raises(HTTPException) as exc_info:
            get_current_user("valid_token")
        
        assert exc_info.value.status_code == 401
        assert "Inactive user" in str(exc_info.value.detail)
    
    @patch('auth.Session')
    @patch('auth.select')
    @patch('auth.unlock_account_if_expired')
    @patch('auth.is_account_locked')
    @patch('auth.jwt.decode')
    def test_get_current_user_locked_account(self, mock_decode, mock_is_locked, mock_unlock, mock_select, mock_session_class):
        """Test getting current user when account is locked"""
        mock_decode.return_value = {"sub": "testuser"}
        
        # Mock database session
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__.return_value = mock_session
        
        # Mock active user
        mock_user = Mock()
        mock_user.is_active = True
        mock_session.exec.return_value.first.return_value = mock_user
        
        # Mock locked account
        mock_is_locked.return_value = True
        
        with pytest.raises(HTTPException) as exc_info:
            get_current_user("valid_token")
        
        assert exc_info.value.status_code == 401
        assert "Account temporarily locked" in str(exc_info.value.detail)


class TestCleanupFunctions:
    """Unit tests for cleanup utility functions"""
    
    @patch('auth.select')
    def test_cleanup_expired_sessions(self, mock_select):
        """Test cleanup of expired user sessions"""
        mock_session = MagicMock()
        
        # Mock expired sessions
        expired_session1 = Mock()
        expired_session2 = Mock()
        mock_session.exec.return_value.all.return_value = [expired_session1, expired_session2]
        
        from auth import cleanup_expired_sessions
        result = cleanup_expired_sessions(mock_session)
        
        assert result == 2
        mock_session.delete.assert_any_call(expired_session1)
        mock_session.delete.assert_any_call(expired_session2)
        mock_session.commit.assert_called_once()
    
    @patch('auth.select')
    def test_cleanup_expired_password_reset_tokens(self, mock_select):
        """Test cleanup of expired password reset tokens"""
        mock_session = MagicMock()
        
        # Mock expired tokens
        expired_token1 = Mock()
        expired_token2 = Mock()
        mock_session.exec.return_value.all.return_value = [expired_token1, expired_token2]
        
        result = cleanup_expired_password_reset_tokens(mock_session)
        
        assert result == 2
        mock_session.delete.assert_any_call(expired_token1)
        mock_session.delete.assert_any_call(expired_token2)
        mock_session.commit.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 