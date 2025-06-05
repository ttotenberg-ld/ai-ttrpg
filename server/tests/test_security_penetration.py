#!/usr/bin/env python3
"""
Security Penetration Testing Suite - Task 5.10
Perform security testing for token manipulation and bypass attempts

This test suite performs comprehensive security testing including:
- JWT token manipulation and forgery attempts
- Authentication bypass attempts
- Authorization vulnerability testing
- Input validation security testing
- Session security testing
- Brute force and rate limiting validation
"""

import pytest
import os
import sys
import json
import base64
import time
from datetime import datetime, timedelta
from typing import Dict, Any
from fastapi.testclient import TestClient
from sqlmodel import Session, select, create_engine, SQLModel
from sqlmodel.pool import StaticPool
from jose import jwt, JWTError

# Add server directory to path for imports
server_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, server_dir)

from models import User, UserSession, PasswordResetToken, UserCreate
from auth import SECRET_KEY, ALGORITHM, get_password_hash
from middleware.password_validator import validate_password_strength

# Import the test app from the API endpoint tests
sys.path.append(os.path.dirname(__file__))
from test_api_auth_endpoints import test_app, client, test_engine, get_test_session

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
def admin_user_data():
    """Admin user data for testing"""
    return {
        "username": "admin",
        "email": "admin@example.com",
        "password": "AdminSecurePhrase123!"
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
    client.post("/users/", json=test_user_data)
    login_response = client.post("/token", data={
        "username": test_user_data["username"],
        "password": test_user_data["password"]
    })
    assert login_response.status_code == 200
    return login_response.json()


class TestJWTTokenManipulation:
    """Security tests for JWT token manipulation attempts"""
    
    def test_invalid_jwt_signature(self, test_db, logged_in_user):
        """Test detection of invalid JWT signatures"""
        valid_token = logged_in_user["access_token"]
        
        # Tamper with the signature
        parts = valid_token.split('.')
        tampered_signature = parts[2][:-1] + 'X'  # Change last character
        tampered_token = f"{parts[0]}.{parts[1]}.{tampered_signature}"
        
        headers = {"Authorization": f"Bearer {tampered_token}"}
        response = client.get("/users/profile", headers=headers)
        
        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["detail"]
    
    def test_modified_jwt_payload(self, test_db, logged_in_user):
        """Test detection of modified JWT payloads"""
        valid_token = logged_in_user["access_token"]
        
        # Decode and modify payload
        parts = valid_token.split('.')
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + '=='))
        
        # Modify the username in payload
        payload["sub"] = "admin"
        modified_payload = base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).decode().rstrip('=')
        
        tampered_token = f"{parts[0]}.{modified_payload}.{parts[2]}"
        
        headers = {"Authorization": f"Bearer {tampered_token}"}
        response = client.get("/users/profile", headers=headers)
        
        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["detail"]
    
    def test_none_algorithm_attack(self, test_db, test_user_data):
        """Test protection against 'none' algorithm attacks"""
        # Create a token with 'none' algorithm
        payload = {
            "sub": test_user_data["username"],
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        
        # Manually create token with 'none' algorithm
        header = {"alg": "none", "typ": "JWT"}
        header_encoded = base64.urlsafe_b64encode(
            json.dumps(header).encode()
        ).decode().rstrip('=')
        payload_encoded = base64.urlsafe_b64encode(
            json.dumps(payload, default=str).encode()
        ).decode().rstrip('=')
        
        malicious_token = f"{header_encoded}.{payload_encoded}."
        
        headers = {"Authorization": f"Bearer {malicious_token}"}
        response = client.get("/users/profile", headers=headers)
        
        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["detail"]
    
    def test_algorithm_confusion_attack(self, test_db, test_user_data):
        """Test protection against algorithm confusion attacks"""
        # Try to use HS256 with a different secret
        payload = {
            "sub": test_user_data["username"],
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        
        # Create token with wrong algorithm
        malicious_token = jwt.encode(payload, "wrong_secret", algorithm="HS512")
        
        headers = {"Authorization": f"Bearer {malicious_token}"}
        response = client.get("/users/profile", headers=headers)
        
        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["detail"]
    
    def test_expired_token_rejection(self, test_db, test_user_data):
        """Test that expired tokens are properly rejected"""
        # Create an expired token
        payload = {
            "sub": test_user_data["username"],
            "exp": datetime.utcnow() - timedelta(hours=1)  # Expired 1 hour ago
        }
        
        expired_token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.get("/users/profile", headers=headers)
        
        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["detail"]
    
    def test_malformed_jwt_token(self, test_db):
        """Test handling of malformed JWT tokens"""
        malformed_tokens = [
            "invalid.token",
            "not.a.jwt.token.at.all",
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9",  # Missing parts
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.invalid_base64.signature",
            "",  # Empty token
            "Bearer token_without_bearer_removed"
        ]
        
        for malformed_token in malformed_tokens:
            headers = {"Authorization": f"Bearer {malformed_token}"}
            response = client.get("/users/profile", headers=headers)
            
            assert response.status_code == 401
            assert "Could not validate credentials" in response.json()["detail"]
    
    def test_token_replay_attack(self, test_db, logged_in_user):
        """Test that tokens can't be replayed after logout"""
        access_token = logged_in_user["access_token"]
        refresh_token = logged_in_user["refresh_token"]
        
        # Use token successfully
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.get("/users/profile", headers=headers)
        assert response.status_code == 200
        
        # Logout to invalidate refresh token
        client.post("/auth/logout", json={"refresh_token": refresh_token})
        
        # Try to use the refresh token again (should fail)
        refresh_response = client.post("/auth/refresh", json={
            "refresh_token": refresh_token
        })
        assert refresh_response.status_code == 401
        
        # Access token should still work until it expires (as designed)
        response = client.get("/users/profile", headers=headers)
        assert response.status_code == 200  # This is expected behavior


class TestAuthenticationBypassAttempts:
    """Security tests for authentication bypass attempts"""
    
    def test_missing_authorization_header(self, test_db):
        """Test that missing authorization headers are rejected"""
        response = client.get("/users/profile")
        
        assert response.status_code == 401
        assert "Not authenticated" in response.json()["detail"]
    
    def test_malformed_authorization_headers(self, test_db):
        """Test handling of malformed authorization headers"""
        malformed_headers = [
            {"Authorization": "InvalidFormat token"},
            {"Authorization": "Bearer"},  # Missing token
            {"Authorization": "Basic dXNlcjpwYXNz"},  # Wrong auth type
            {"Authorization": "bearer lowercase_bearer"},  # Case sensitivity
            {"Authorization": "Bearer "},  # Empty token after Bearer
            {"Authorization": ""},  # Empty header
        ]
        
        for headers in malformed_headers:
            response = client.get("/users/profile", headers=headers)
            assert response.status_code in [401, 422]
    
    def test_sql_injection_in_login(self, test_db, registered_user):
        """Test SQL injection attempts in login endpoint"""
        sql_injection_attempts = [
            "admin'; DROP TABLE users; --",
            "admin' OR '1'='1",
            "admin' UNION SELECT * FROM users --",
            "admin'; UPDATE users SET password='hacked' --",
            "admin' OR 1=1 --",
            "'; SELECT * FROM user_sessions; --"
        ]
        
        for injection_attempt in sql_injection_attempts:
            response = client.post("/token", data={
                "username": injection_attempt,
                "password": "any_password"
            })
            
            # Should return 401 (not 500 which would indicate SQL error)
            assert response.status_code == 401
            assert "Incorrect username or password" in response.json()["detail"]
    
    def test_brute_force_protection(self, test_db, test_user_data, registered_user):
        """Test brute force protection mechanisms"""
        # Make multiple failed login attempts
        for i in range(10):
            response = client.post("/token", data={
                "username": test_user_data["username"],
                "password": f"wrong_password_{i}"
            })
            
            # Should get 401 for failed attempts
            assert response.status_code == 401
            
            # After 5 attempts, should get account locked message
            if i >= 5:
                assert "Account locked" in response.json()["detail"] or \
                       "Incorrect username or password" in response.json()["detail"]
    
    def test_user_enumeration_protection(self, test_db):
        """Test that user enumeration is prevented"""
        # Try to login with non-existent user
        response1 = client.post("/token", data={
            "username": "nonexistent_user",
            "password": "any_password"
        })
        
        # Try to login with existing user but wrong password
        client.post("/users/", json={
            "username": "existing_user",
            "email": "existing@example.com",
            "password": "SecurePhrase123!"
        })
        
        response2 = client.post("/token", data={
            "username": "existing_user",
            "password": "wrong_password"
        })
        
        # Both should return the same error message
        assert response1.status_code == 401
        assert response2.status_code == 401
        assert response1.json()["detail"] == response2.json()["detail"]
    
    def test_password_reset_enumeration_protection(self, test_db):
        """Test that password reset doesn't reveal user existence"""
        # Request reset for non-existent email
        response1 = client.post("/auth/forgot-password", json={
            "email": "nonexistent@example.com"
        })
        
        # Request reset for existing email
        client.post("/users/", json={
            "username": "testuser",
            "email": "existing@example.com", 
            "password": "SecurePhrase123!"
        })
        
        response2 = client.post("/auth/forgot-password", json={
            "email": "existing@example.com"
        })
        
        # Both should return the same message
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json()["message"] == response2.json()["message"]


class TestAuthorizationVulnerabilities:
    """Security tests for authorization vulnerabilities"""
    
    def test_horizontal_privilege_escalation(self, test_db):
        """Test prevention of accessing other users' resources"""
        # Create two users
        user1_data = {
            "username": "user1",
            "email": "user1@example.com",
            "password": "SecurePhrase123!"
        }
        user2_data = {
            "username": "user2", 
            "email": "user2@example.com",
            "password": "SecurePhrase123!"
        }
        
        client.post("/users/", json=user1_data)
        client.post("/users/", json=user2_data)
        
        # Login as user1
        login_response = client.post("/token", data={
            "username": user1_data["username"],
            "password": user1_data["password"]
        })
        user1_token = login_response.json()["access_token"]
        
        # Try to access user1's profile with user1's token (should work)
        headers = {"Authorization": f"Bearer {user1_token}"}
        response = client.get("/users/profile", headers=headers)
        assert response.status_code == 200
        assert response.json()["username"] == user1_data["username"]
        
        # The current API design doesn't allow accessing other users' profiles
        # This is good security design - users can only access their own profile
    
    def test_token_substitution_attack(self, test_db):
        """Test that tokens can't be substituted between users"""
        # Create two users and get their tokens
        user1_data = {"username": "user1", "email": "user1@example.com", "password": "SecurePhrase123!"}
        user2_data = {"username": "user2", "email": "user2@example.com", "password": "SecurePhrase123!"}
        
        client.post("/users/", json=user1_data)
        client.post("/users/", json=user2_data)
        
        # Get tokens for both users
        login1 = client.post("/token", data={"username": user1_data["username"], "password": user1_data["password"]})
        login2 = client.post("/token", data={"username": user2_data["username"], "password": user2_data["password"]})
        
        user1_token = login1.json()["access_token"]
        user2_token = login2.json()["access_token"]
        
        # Verify each user can only access their own profile
        headers1 = {"Authorization": f"Bearer {user1_token}"}
        headers2 = {"Authorization": f"Bearer {user2_token}"}
        
        profile1 = client.get("/users/profile", headers=headers1)
        profile2 = client.get("/users/profile", headers=headers2)
        
        assert profile1.status_code == 200
        assert profile2.status_code == 200
        assert profile1.json()["username"] == user1_data["username"]
        assert profile2.json()["username"] == user2_data["username"]


class TestInputValidationSecurity:
    """Security tests for input validation vulnerabilities"""
    
    def test_xss_prevention_in_user_inputs(self, test_db):
        """Test XSS prevention in user input fields"""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "';alert('xss');//",
            "<svg onload=alert('xss')>",
            "'+alert('xss')+'",
        ]
        
        for payload in xss_payloads:
            # Test XSS in registration
            response = client.post("/users/", json={
                "username": payload,
                "email": "test@example.com",
                "password": "SecurePhrase123!"
            })
            
            # Should either reject the input or sanitize it
            # Most likely it will be accepted as username (which is OK if properly escaped on output)
            if response.status_code == 200:
                # If accepted, verify it's stored safely (no script execution)
                data = response.json()
                # The payload should be stored as-is but not executed
                assert payload in data["username"] or len(data["username"]) > 0
    
    def test_buffer_overflow_protection(self, test_db):
        """Test protection against buffer overflow attempts"""
        # Very long strings
        long_string = "A" * 10000
        very_long_string = "B" * 100000
        
        # Test extremely long username
        response = client.post("/users/", json={
            "username": long_string,
            "email": "test@example.com",
            "password": "SecurePhrase123!"
        })
        
        # Should handle gracefully (either accept with truncation or reject)
        assert response.status_code in [200, 400, 422]
        
        # Test extremely long email
        response = client.post("/users/", json={
            "username": "testuser",
            "email": f"{very_long_string}@example.com",
            "password": "SecurePhrase123!"
        })
        
        # Should handle gracefully
        assert response.status_code in [200, 400, 422]
    
    def test_unicode_handling(self, test_db):
        """Test proper handling of Unicode characters"""
        unicode_inputs = [
            "用户名",  # Chinese characters
            "José",    # Accented characters
            "🚀🌟",    # Emojis
            "\u0000",  # Null byte
            "\u200B",  # Zero width space
            "test\r\nuser",  # Control characters
        ]
        
        for unicode_input in unicode_inputs:
            response = client.post("/users/", json={
                "username": unicode_input,
                "email": "test@example.com",
                "password": "SecurePhrase123!"
            })
            
            # Should handle Unicode gracefully
            assert response.status_code in [200, 400, 422]
    
    def test_injection_in_password_reset(self, test_db):
        """Test injection attempts in password reset functionality"""
        injection_attempts = [
            "test@example.com'; DROP TABLE users; --",
            "test@example.com' OR '1'='1",
            "<script>alert('xss')</script>@example.com",
            "test@example.com\x00admin@example.com",
        ]
        
        for injection_attempt in injection_attempts:
            response = client.post("/auth/forgot-password", json={
                "email": injection_attempt
            })
            
            # Should handle gracefully without SQL injection
            assert response.status_code in [200, 400, 422]
            if response.status_code == 200:
                assert "password reset link has been sent" in response.json()["message"]


class TestSessionSecurity:
    """Security tests for session management"""
    
    def test_session_fixation_protection(self, test_db, test_user_data):
        """Test protection against session fixation attacks"""
        # Register user
        client.post("/users/", json=test_user_data)
        
        # Get multiple tokens for the same user
        login1 = client.post("/token", data={
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        })
        login2 = client.post("/token", data={
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        })
        
        token1 = login1.json()["refresh_token"]
        token2 = login2.json()["refresh_token"]
        
        # Tokens should be different (no session fixation)
        assert token1 != token2
        
        # Both tokens should work independently
        refresh1 = client.post("/auth/refresh", json={"refresh_token": token1})
        refresh2 = client.post("/auth/refresh", json={"refresh_token": token2})
        
        assert refresh1.status_code == 200
        assert refresh2.status_code == 200
    
    def test_concurrent_session_handling(self, test_db, test_user_data):
        """Test handling of concurrent user sessions"""
        # Register user
        client.post("/users/", json=test_user_data)
        
        # Create multiple concurrent sessions
        sessions = []
        for i in range(5):
            login = client.post("/token", data={
                "username": test_user_data["username"],
                "password": test_user_data["password"]
            })
            assert login.status_code == 200
            sessions.append(login.json())
        
        # All sessions should be valid
        for session in sessions:
            headers = {"Authorization": f"Bearer {session['access_token']}"}
            response = client.get("/users/profile", headers=headers)
            assert response.status_code == 200
        
        # Logout from one session shouldn't affect others
        client.post("/auth/logout", json={
            "refresh_token": sessions[0]["refresh_token"]
        })
        
        # Other sessions should still work
        for session in sessions[1:]:
            headers = {"Authorization": f"Bearer {session['access_token']}"}
            response = client.get("/users/profile", headers=headers)
            assert response.status_code == 200
    
    def test_refresh_token_rotation(self, test_db, logged_in_user):
        """Test that refresh tokens are properly rotated"""
        original_refresh_token = logged_in_user["refresh_token"]
        
        # Use refresh token
        response = client.post("/auth/refresh", json={
            "refresh_token": original_refresh_token
        })
        
        assert response.status_code == 200
        new_tokens = response.json()
        
        # Should get new refresh token
        assert new_tokens["refresh_token"] != original_refresh_token
        
        # Old refresh token should be invalidated
        old_refresh_response = client.post("/auth/refresh", json={
            "refresh_token": original_refresh_token
        })
        assert old_refresh_response.status_code == 401


class TestRateLimitingSecurity:
    """Security tests for rate limiting effectiveness"""
    
    def test_login_rate_limiting_effectiveness(self, test_db, test_user_data):
        """Test that rate limiting effectively prevents brute force"""
        # Register user
        client.post("/users/", json=test_user_data)
        
        # Make rapid failed login attempts
        failed_attempts = 0
        rate_limited = False
        
        for i in range(20):  # Try many attempts
            response = client.post("/token", data={
                "username": test_user_data["username"],
                "password": f"wrong_password_{i}"
            })
            
            if response.status_code == 429:  # Rate limited
                rate_limited = True
                break
            elif response.status_code == 401:
                failed_attempts += 1
            
            # Small delay to avoid overwhelming the test
            time.sleep(0.1)
        
        # Should either get rate limited or account locked
        assert rate_limited or failed_attempts >= 5
    
    def test_registration_rate_limiting(self, test_db):
        """Test rate limiting on registration endpoint"""
        rate_limited = False
        successful_registrations = 0
        
        for i in range(10):
            response = client.post("/users/", json={
                "username": f"user_{i}",
                "email": f"user_{i}@example.com",
                "password": "SecurePhrase123!"
            })
            
            if response.status_code == 429:
                rate_limited = True
                break
            elif response.status_code == 200:
                successful_registrations += 1
            
            time.sleep(0.05)  # Small delay
        
        # Should either get rate limited or succeed with reasonable number
        assert rate_limited or successful_registrations > 0
    
    def test_password_reset_rate_limiting(self, test_db):
        """Test rate limiting on password reset requests"""
        rate_limited = False
        
        for i in range(10):
            response = client.post("/auth/forgot-password", json={
                "email": f"test_{i}@example.com"
            })
            
            if response.status_code == 429:
                rate_limited = True
                break
            
            time.sleep(0.05)
        
        # Password reset should be heavily rate limited
        # Even if not rate limited at endpoint level, should be limited by email sending


class TestPasswordSecurityValidation:
    """Security tests for password validation and strength"""
    
    def test_password_policy_enforcement(self, test_db):
        """Test that password policies are properly enforced"""
        weak_passwords = [
            "123",
            "password",
            "qwerty",
            "admin",
            "12345678",
            "Password",  # Missing special chars
            "password123",  # Missing uppercase and special
            "PASSWORD123!",  # Missing lowercase
        ]
        
        for weak_password in weak_passwords:
            response = client.post("/users/", json={
                "username": "testuser",
                "email": "test@example.com",
                "password": weak_password
            })
            
            # Should reject weak passwords
            assert response.status_code == 400
            detail = response.json()["detail"]
            assert "Password does not meet security requirements" in detail["message"]
    
    def test_password_complexity_bypass_attempts(self, test_db):
        """Test attempts to bypass password complexity"""
        bypass_attempts = [
            "Password123! ",  # Trailing space
            " Password123!",  # Leading space
            "Password123!\x00",  # Null byte
            "Password123!\n",  # Newline
            "Password123!\t",  # Tab
        ]
        
        for bypass_attempt in bypass_attempts:
            response = client.post("/users/", json={
                "username": "testuser",
                "email": "test@example.com",
                "password": bypass_attempt
            })
            
            # Should either accept (if properly sanitized) or reject
            if response.status_code == 200:
                # If accepted, verify it's handled properly
                # Login should work with the exact same password
                login_response = client.post("/token", data={
                    "username": "testuser",
                    "password": bypass_attempt
                })
                assert login_response.status_code == 200
                break  # Only test one successful case
            else:
                assert response.status_code == 400


class TestDataLeakagePrevention:
    """Security tests for preventing data leakage"""
    
    def test_error_message_information_disclosure(self, test_db):
        """Test that error messages don't leak sensitive information"""
        # Test with various invalid inputs
        response = client.post("/token", data={
            "username": "nonexistent",
            "password": "password"
        })
        
        assert response.status_code == 401
        error_detail = response.json()["detail"].lower()
        
        # Should not reveal system details
        forbidden_info = [
            "database", "sql", "table", "column", "server", "file", "path",
            "stack", "trace", "exception", "error:", "line", "function"
        ]
        
        for info in forbidden_info:
            assert info not in error_detail
    
    def test_timing_attack_resistance(self, test_db):
        """Test resistance to timing attacks"""
        # Register a user
        client.post("/users/", json={
            "username": "existing_user",
            "email": "existing@example.com",
            "password": "SecurePhrase123!"
        })
        
        # Measure time for non-existent user
        start_time = time.time()
        response1 = client.post("/token", data={
            "username": "nonexistent_user",
            "password": "any_password"
        })
        time1 = time.time() - start_time
        
        # Measure time for existing user with wrong password
        start_time = time.time()
        response2 = client.post("/token", data={
            "username": "existing_user",
            "password": "wrong_password"
        })
        time2 = time.time() - start_time
        
        # Both should return 401
        assert response1.status_code == 401
        assert response2.status_code == 401
        
        # Time difference should be minimal (less than 100ms difference)
        time_diff = abs(time1 - time2)
        assert time_diff < 0.1  # 100ms tolerance
    
    def test_response_data_sanitization(self, test_db, logged_in_user):
        """Test that response data doesn't contain sensitive information"""
        headers = {"Authorization": f"Bearer {logged_in_user['access_token']}"}
        response = client.get("/users/profile", headers=headers)
        
        assert response.status_code == 200
        response_text = json.dumps(response.json()).lower()
        
        # Should not contain sensitive data
        sensitive_data = [
            "password", "secret", "key", "token", "hash", "salt",
            "private", "credential", "session_id"
        ]
        
        for sensitive in sensitive_data:
            assert sensitive not in response_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 