#!/usr/bin/env python3
"""
API Endpoints Test - Task 1.8, 1.9, 1.10 Verification
Tests the authentication API endpoints work correctly
"""

import sys
import os
from fastapi.testclient import TestClient

# Add the server directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import app

# Create test client
client = TestClient(app)

def test_task_1_8_login_returns_both_tokens():
    """Test 1.8: Verify login endpoint returns both access and refresh tokens"""
    print("🧪 Testing Task 1.8: Login endpoint returns both access and refresh tokens")
    
    # First register a user
    register_response = client.post(
        "/users/",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123"
        }
    )
    
    if register_response.status_code != 200:
        print(f"  ❌ User registration failed: {register_response.json()}")
        return False
    
    print("  ✓ User registered successfully")
    
    # Login and check response
    login_response = client.post(
        "/token",
        data={
            "username": "testuser",
            "password": "password123"
        }
    )
    
    if login_response.status_code != 200:
        print(f"  ❌ Login failed: {login_response.json()}")
        return False
    
    data = login_response.json()
    
    # Verify both tokens are returned
    required_fields = ["access_token", "refresh_token", "token_type"]
    for field in required_fields:
        if field not in data:
            print(f"  ❌ Missing field in response: {field}")
            return False
    
    if data["token_type"] != "bearer":
        print(f"  ❌ Wrong token type: {data['token_type']}")
        return False
    
    if len(data["access_token"]) < 50:
        print(f"  ❌ Access token too short: {len(data['access_token'])}")
        return False
    
    if len(data["refresh_token"]) < 30:
        print(f"  ❌ Refresh token too short: {len(data['refresh_token'])}")
        return False
    
    print("  ✅ Login endpoint correctly returns both access and refresh tokens")
    return True, data

def test_task_1_9_logout_blacklists_refresh_token():
    """Test 1.9: Verify logout endpoint blacklists refresh tokens"""
    print("\n🧪 Testing Task 1.9: Logout endpoint blacklists refresh tokens")
    
    # Get tokens from login
    success, tokens = test_task_1_8_login_returns_both_tokens()
    if not success:
        print("  ❌ Cannot test logout without successful login")
        return False
    
    refresh_token = tokens["refresh_token"]
    
    # Logout
    logout_response = client.post(
        "/auth/logout",
        json={"refresh_token": refresh_token}
    )
    
    if logout_response.status_code != 200:
        print(f"  ❌ Logout failed: {logout_response.json()}")
        return False
    
    logout_data = logout_response.json()
    if "Successfully logged out" not in logout_data.get("message", ""):
        print(f"  ❌ Unexpected logout message: {logout_data}")
        return False
    
    print("  ✓ Logout endpoint responded correctly")
    
    # Try to use the refresh token (should fail)
    refresh_response = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    
    if refresh_response.status_code != 401:
        print(f"  ❌ Refresh token still valid after logout: {refresh_response.status_code}")
        return False
    
    print("  ✅ Logout endpoint correctly blacklists refresh tokens")
    return True

def test_task_1_10_refresh_token_endpoint():
    """Test 1.10: Verify refresh token endpoint for token renewal"""
    print("\n🧪 Testing Task 1.10: Refresh token endpoint for token renewal")
    
    # Register a new user for this test
    register_response = client.post(
        "/users/",
        json={
            "username": "refreshtestuser",
            "email": "refresh@example.com",
            "password": "password123"
        }
    )
    
    if register_response.status_code != 200:
        print(f"  ❌ User registration failed: {register_response.json()}")
        return False
    
    # Login to get tokens
    login_response = client.post(
        "/token",
        data={
            "username": "refreshtestuser",
            "password": "password123"
        }
    )
    
    if login_response.status_code != 200:
        print(f"  ❌ Login failed: {login_response.json()}")
        return False
    
    original_tokens = login_response.json()
    refresh_token = original_tokens["refresh_token"]
    
    print("  ✓ Got initial tokens")
    
    # Use refresh token to get new tokens
    refresh_response = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    
    if refresh_response.status_code != 200:
        print(f"  ❌ Refresh failed: {refresh_response.json()}")
        return False
    
    new_tokens = refresh_response.json()
    
    # Verify new tokens are returned
    required_fields = ["access_token", "refresh_token", "token_type"]
    for field in required_fields:
        if field not in new_tokens:
            print(f"  ❌ Missing field in refresh response: {field}")
            return False
    
    # Verify new tokens are different from original
    if new_tokens["access_token"] == original_tokens["access_token"]:
        print("  ❌ New access token is same as original")
        return False
    
    if new_tokens["refresh_token"] == refresh_token:
        print("  ❌ New refresh token is same as original")
        return False
    
    print("  ✅ Refresh token endpoint correctly generates new tokens")
    return True

def test_task_1_7_user_profile_endpoints():
    """Test 1.7: Verify user profile management endpoints"""
    print("\n🧪 Testing Task 1.7: User profile management endpoints")
    
    # Register and login
    register_response = client.post(
        "/users/",
        json={
            "username": "profiletestuser",
            "email": "profile@example.com",
            "password": "password123"
        }
    )
    
    if register_response.status_code != 200:
        print(f"  ❌ User registration failed: {register_response.json()}")
        return False
    
    login_response = client.post(
        "/token",
        data={
            "username": "profiletestuser",
            "password": "password123"
        }
    )
    
    if login_response.status_code != 200:
        print(f"  ❌ Login failed: {login_response.json()}")
        return False
    
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Test GET profile
    profile_response = client.get("/users/profile", headers=headers)
    
    if profile_response.status_code != 200:
        print(f"  ❌ Get profile failed: {profile_response.json()}")
        return False
    
    profile_data = profile_response.json()
    
    required_fields = ["username", "email", "email_verified", "is_active"]
    for field in required_fields:
        if field not in profile_data:
            print(f"  ❌ Missing field in profile: {field}")
            return False
    
    if profile_data["username"] != "profiletestuser":
        print(f"  ❌ Wrong username in profile: {profile_data['username']}")
        return False
    
    print("  ✓ GET profile endpoint works correctly")
    
    # Test PATCH profile
    update_response = client.patch(
        "/users/profile",
        headers=headers,
        json={"username": "updatedusername"}
    )
    
    if update_response.status_code != 200:
        print(f"  ❌ Update profile failed: {update_response.json()}")
        return False
    
    updated_data = update_response.json()
    
    if updated_data["username"] != "updatedusername":
        print(f"  ❌ Username not updated: {updated_data['username']}")
        return False
    
    print("  ✅ User profile management endpoints work correctly")
    return True

def run_api_tests():
    """Run API endpoint tests for tasks 1.7-1.10"""
    print("🔗 Testing Authentication API Endpoints")
    print("=" * 50)
    
    tests = [
        ("1.8", "Login returns both tokens", test_task_1_8_login_returns_both_tokens),
        ("1.9", "Logout blacklists refresh tokens", test_task_1_9_logout_blacklists_refresh_token),
        ("1.10", "Refresh token endpoint", test_task_1_10_refresh_token_endpoint),
        ("1.7", "User profile endpoints", test_task_1_7_user_profile_endpoints),
    ]
    
    passed = 0
    total = len(tests)
    
    for task_num, description, test_func in tests:
        try:
            result = test_func()
            if result is True or (isinstance(result, tuple) and result[0] is True):
                passed += 1
        except Exception as e:
            print(f"  ❌ Task {task_num} failed with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 API ENDPOINT TEST RESULTS")
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 ALL API ENDPOINT TESTS PASSED!")
        print("✅ Tasks 1.7, 1.8, 1.9, 1.10 - VERIFIED WORKING")
        return True
    else:
        print(f"\n⚠️  {total - passed} tests failed")
        return False

if __name__ == "__main__":
    success = run_api_tests()
    sys.exit(0 if success else 1) 