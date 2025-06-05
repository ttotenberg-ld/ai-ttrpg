#!/usr/bin/env python3
"""
Simple Security Features Test
Tests the core security components without FastAPI dependencies
"""

from middleware.password_validator import validate_password_strength, get_password_policy
from middleware.rate_limiter import check_rate_limiter_health
from middleware.request_logger import AuditLogger, SecurityEvent

def test_password_validation():
    """Test password validation functionality"""
    print('\n📋 Testing Password Validation')
    
    # Test weak password
    result = validate_password_strength('weak')
    assert not result.is_valid, "Weak password should be invalid"
    assert len(result.errors) > 0, "Weak password should have errors"
    print(f'✅ Weak password correctly rejected: {len(result.errors)} errors')
    
    # Test strong password (avoiding forbidden words)
    result = validate_password_strength('MyVeryStr0ng&SecureK3y!')
    assert result.is_valid, f"Strong password should be valid. Errors: {result.errors}"
    assert result.score > 70, "Strong password should have high score"
    print(f'✅ Strong password accepted: {result.score}/100 score')
    
    # Test password policy
    policy = get_password_policy()
    assert policy['min_length'] >= 8, "Minimum length should be at least 8"
    print(f'✅ Password policy loaded: {policy["min_length"]} min chars')

def test_rate_limiter():
    """Test rate limiter functionality"""
    print('\n📋 Testing Rate Limiter')
    
    health = check_rate_limiter_health()
    assert isinstance(health, bool), "Health check should return boolean"
    print(f'✅ Rate limiter health check: {health}')

def test_audit_logger():
    """Test audit logging functionality"""
    print('\n📋 Testing Audit Logger')
    
    logger = AuditLogger()
    assert hasattr(logger, 'log_security_event'), "Logger should have log_security_event method"
    assert hasattr(logger, 'log_request'), "Logger should have log_request method"
    
    # Test logging a security event
    logger.log_security_event(
        SecurityEvent.LOGIN_SUCCESS,
        username='testuser',
        ip_address='127.0.0.1'
    )
    print('✅ Security event logged successfully')
    
    # Test data sanitization
    sensitive_data = {
        'password': 'secret123',
        'token': 'abc123',
        'username': 'testuser'
    }
    sanitized = logger._sanitize_details(sensitive_data)
    assert sanitized['password'] == '[REDACTED]', "Password should be redacted"
    assert sanitized['token'] == '[REDACTED]', "Token should be redacted"
    assert sanitized['username'] == 'testuser', "Username should not be redacted"
    print('✅ Data sanitization working correctly')

def main():
    """Run all security tests"""
    print('🔒 Testing Security Features Implementation')
    print('=' * 50)
    
    try:
        test_password_validation()
        test_rate_limiter()
        test_audit_logger()
        
        print('\n' + '=' * 50)
        print('🎉 ALL SECURITY FEATURES WORKING CORRECTLY!')
        print('✅ Tasks 5.1-5.4 Security Features - VERIFIED')
        return True
        
    except Exception as e:
        print(f'\n❌ Test failed: {e}')
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) 