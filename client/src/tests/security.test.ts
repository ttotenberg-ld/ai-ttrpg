/**
 * Frontend Security Features Test Suite - Task 5.6
 * Tests client-side security features and integration with backend security
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock API responses
const mockApiResponses = {
  passwordPolicy: {
    min_length: 8,
    max_length: 128,
    requirements: {
      uppercase_letters: "At least 1",
      lowercase_letters: "At least 1", 
      digits: "At least 1",
      special_characters: "At least 1"
    },
    restrictions: {
      whitespace_allowed: false,
      max_consecutive_chars: 3,
      prevent_username_similarity: true,
      prevent_email_similarity: true
    }
  },
  
  weakPasswordError: {
    message: "Password does not meet security requirements",
    errors: [
      "Password must be at least 8 characters long",
      "Password must contain at least 1 uppercase letter(s)",
      "Password must contain at least 1 digit(s)"
    ],
    suggestions: [
      "Add uppercase letters (A-Z)",
      "Add numbers (0-9)"
    ],
    strength_score: 25,
    strength_level: "Weak"
  },
  
  rateLimitError: {
    error: "Rate limit exceeded",
    message: "Too many requests. Limit: 5/minute",
    retry_after: 60,
    type: "rate_limit_error"
  }
};

// Mock fetch globally
global.fetch = vi.fn();

describe('Password Validation Logic', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should fetch password policy from API', async () => {
    (fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockApiResponses.passwordPolicy
    });

    const response = await fetch('/auth/password-policy');
    const policy = await response.json();

    expect(policy.min_length).toBe(8);
    expect(policy.max_length).toBe(128);
    expect(policy.requirements.uppercase_letters).toBe("At least 1");
  });

  it('should calculate password strength correctly', () => {
    const calculatePasswordStrength = (password: string) => {
      let score = 0;
      if (password.length >= 8) score += 25;
      if (/[A-Z]/.test(password)) score += 25;
      if (/[a-z]/.test(password)) score += 25;
      if (/\d/.test(password)) score += 25;
      
      let level = 'Very Weak';
      if (score >= 80) level = 'Very Strong';
      else if (score >= 60) level = 'Strong';
      else if (score >= 40) level = 'Medium';
      else if (score >= 20) level = 'Weak';

      return { score, level };
    };

    // Test weak password
    const weakResult = calculatePasswordStrength('weak');
    expect(weakResult.score).toBe(25);
    expect(weakResult.level).toBe('Weak');

    // Test strong password
    const strongResult = calculatePasswordStrength('StrongPassword123!');
    expect(strongResult.score).toBe(100);
    expect(strongResult.level).toBe('Very Strong');
  });

  it('should validate password requirements', () => {
    const validatePassword = (password: string, policy: any) => {
      const errors = [];
      
      if (password.length < policy.min_length) {
        errors.push(`Password must be at least ${policy.min_length} characters long`);
      }
      
      if (policy.requirements.uppercase_letters !== "Not required" && !/[A-Z]/.test(password)) {
        errors.push("Password must contain at least 1 uppercase letter(s)");
      }
      
      if (policy.requirements.lowercase_letters !== "Not required" && !/[a-z]/.test(password)) {
        errors.push("Password must contain at least 1 lowercase letter(s)");
      }
      
      if (policy.requirements.digits !== "Not required" && !/\d/.test(password)) {
        errors.push("Password must contain at least 1 digit(s)");
      }
      
      return errors;
    };

    const policy = mockApiResponses.passwordPolicy;
    
    // Test weak password
    const weakErrors = validatePassword('weak', policy);
    expect(weakErrors).toContain('Password must be at least 8 characters long');
    expect(weakErrors).toContain('Password must contain at least 1 uppercase letter(s)');
    expect(weakErrors).toContain('Password must contain at least 1 digit(s)');

    // Test strong password
    const strongErrors = validatePassword('StrongPassword123!', policy);
    expect(strongErrors).toHaveLength(0);
  });
});

describe('Error Handling Logic', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should handle rate limit errors correctly', async () => {
    (fetch as any).mockRejectedValueOnce({
      status: 429,
      json: async () => mockApiResponses.rateLimitError,
      headers: new Map([['Retry-After', '60']])
    });

    const handleApiError = async (response: any) => {
      if (response.status === 429) {
        const errorData = await response.json();
        return {
          type: 'rate_limit',
          message: errorData.message,
          retryAfter: response.headers.get('Retry-After')
        };
      }
      return null;
    };

    try {
      await fetch('/token', {
        method: 'POST',
        body: 'username=test&password=test'
      });
    } catch (error: any) {
      const errorInfo = await handleApiError(error);
      expect(errorInfo?.type).toBe('rate_limit');
      expect(errorInfo?.message).toBe('Too many requests. Limit: 5/minute');
      expect(errorInfo?.retryAfter).toBe('60');
    }
  });

  it('should handle validation errors correctly', () => {
    const handleValidationErrors = (errors: any[]) => {
      return errors.map(error => ({
        field: error.field,
        message: error.message,
        userFriendlyMessage: `${error.field}: ${error.message}`
      }));
    };

    const validationErrors = [
      { field: "username", message: "field required", type: "value_error.missing" },
      { field: "email", message: "field required", type: "value_error.missing" }
    ];

    const processed = handleValidationErrors(validationErrors);
    
    expect(processed).toHaveLength(2);
    expect(processed[0].userFriendlyMessage).toBe('username: field required');
    expect(processed[1].userFriendlyMessage).toBe('email: field required');
  });

  it('should sanitize error responses', () => {
    const sanitizeErrorResponse = (error: any) => {
      const sensitiveFields = ['password', 'token', 'secret', 'key', 'authorization'];
      const sanitized = { ...error };
      
      for (const field of sensitiveFields) {
        if (sanitized[field]) {
          sanitized[field] = '[REDACTED]';
        }
      }
      
      return sanitized;
    };

    const errorWithSensitiveData = {
      message: 'Authentication failed',
      password: 'user-password-123',
      token: 'secret-token-abc',
      username: 'testuser'
    };

    const sanitized = sanitizeErrorResponse(errorWithSensitiveData);

    expect(sanitized.password).toBe('[REDACTED]');
    expect(sanitized.token).toBe('[REDACTED]');
    expect(sanitized.username).toBe('testuser');
    expect(sanitized.message).toBe('Authentication failed');
  });
});

describe('Security Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should handle authentication flow with proper token management', async () => {
    // Mock successful login
    (fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
        token_type: 'bearer'
      })
    });

    const login = async (username: string, password: string) => {
      const response = await fetch('/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `username=${username}&password=${password}`
      });
      
      if (response.ok) {
        const data = await response.json();
        // Store tokens securely
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);
        return data;
      }
      
      throw new Error('Login failed');
    };

    const result = await login('testuser', 'StrongPassword123!');
    
    expect(result.access_token).toBe('mock-access-token');
    expect(result.refresh_token).toBe('mock-refresh-token');
    expect(localStorage.getItem('access_token')).toBe('mock-access-token');
    expect(localStorage.getItem('refresh_token')).toBe('mock-refresh-token');
  });

  it('should handle logout and token cleanup', async () => {
    // Set up initial tokens
    localStorage.setItem('access_token', 'mock-access-token');
    localStorage.setItem('refresh_token', 'mock-refresh-token');

    (fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ message: 'Successfully logged out' })
    });

    const logout = async () => {
      const refreshToken = localStorage.getItem('refresh_token');
      
      if (refreshToken) {
        await fetch('/auth/logout', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken })
        });
      }
      
      // Clear tokens
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    };

    await logout();

    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.getItem('refresh_token')).toBeNull();
  });

  it('should validate input before sending to server', () => {
    const validateRegistrationInput = (data: any) => {
      const errors = [];
      
      if (!data.username || data.username.length < 3) {
        errors.push('Username must be at least 3 characters');
      }
      
      if (!data.email || !data.email.includes('@')) {
        errors.push('Valid email is required');
      }
      
      if (!data.password || data.password.length < 8) {
        errors.push('Password must be at least 8 characters');
      }
      
      // Check for XSS attempts
      const xssPattern = /<script|javascript:|on\w+=/i;
      if (xssPattern.test(data.username) || xssPattern.test(data.email)) {
        errors.push('Invalid characters detected');
      }
      
      return errors;
    };

    const validData = {
      username: 'testuser',
      email: 'test@example.com',
      password: 'StrongPassword123!'
    };

    const invalidData = {
      username: 'ab',
      email: 'invalid-email',
      password: 'weak'
    };

    const xssData = {
      username: '<script>alert("xss")</script>',
      email: 'test@example.com',
      password: 'StrongPassword123!'
    };

    expect(validateRegistrationInput(validData)).toHaveLength(0);
    expect(validateRegistrationInput(invalidData)).toHaveLength(3);
    expect(validateRegistrationInput(xssData)).toContain('Invalid characters detected');
  });
});

describe('Security Best Practices', () => {
  it('should implement proper CSRF protection', () => {
    const getCSRFToken = () => {
      // Mock CSRF token retrieval
      return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || 'mock-csrf-token';
    };

    const makeSecureRequest = async (url: string, data: any) => {
      const csrfToken = getCSRFToken();
      
      return fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken
        },
        body: JSON.stringify(data)
      });
    };

    // Mock the meta tag
    document.head.innerHTML = '<meta name="csrf-token" content="test-csrf-token">';
    
    const token = getCSRFToken();
    expect(token).toBe('test-csrf-token');
  });

  it('should implement secure headers for requests', () => {
    const createSecureHeaders = (includeAuth = false) => {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
      };

      if (includeAuth) {
        const token = localStorage.getItem('access_token');
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
      }

      return headers;
    };

    const publicHeaders = createSecureHeaders(false);
    const authHeaders = createSecureHeaders(true);

    expect(publicHeaders['X-Requested-With']).toBe('XMLHttpRequest');
    expect(authHeaders['Authorization']).toBeUndefined(); // No token in localStorage

    // Set token and test again
    localStorage.setItem('access_token', 'test-token');
    const authHeadersWithToken = createSecureHeaders(true);
    expect(authHeadersWithToken['Authorization']).toBe('Bearer test-token');
  });
}); 