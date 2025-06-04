import React, { useState } from 'react';
import type { FormEvent } from 'react';
import { useAuth } from '../../hooks/useAuth';
import type { RegisterRequest } from '../../types/api';

interface RegisterFormProps {
  onSuccess?: () => void;
  onSwitchToLogin?: () => void;
}

interface FormErrors {
  username?: string;
  email?: string;
  password?: string;
  confirm_password?: string;
  general?: string;
}

interface RegistrationStep {
  step: 'register' | 'verify-email' | 'success';
  email?: string;
}

const styles = {
  container: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: '100vh',
    padding: '20px',
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  } as React.CSSProperties,
  
  form: {
    background: 'white',
    padding: '40px',
    borderRadius: '12px',
    boxShadow: '0 10px 30px rgba(0, 0, 0, 0.1)',
    width: '100%',
    maxWidth: '400px',
  } as React.CSSProperties,
  
  title: {
    textAlign: 'center',
    margin: '0 0 8px 0',
    color: '#333',
    fontSize: '28px',
    fontWeight: '600',
  } as React.CSSProperties,
  
  subtitle: {
    textAlign: 'center',
    margin: '0 0 32px 0',
    color: '#666',
    fontSize: '14px',
  } as React.CSSProperties,
  
  formGroup: {
    marginBottom: '24px',
  } as React.CSSProperties,
  
  label: {
    display: 'block',
    marginBottom: '6px',
    color: '#333',
    fontWeight: '500',
    fontSize: '14px',
  } as React.CSSProperties,
  
  input: {
    width: '100%',
    padding: '12px 16px',
    border: '2px solid #e1e5e9',
    borderRadius: '8px',
    fontSize: '16px',
    transition: 'border-color 0.2s ease',
    boxSizing: 'border-box',
  } as React.CSSProperties,
  
  inputError: {
    borderColor: '#e74c3c',
  } as React.CSSProperties,
  
  passwordContainer: {
    position: 'relative',
  } as React.CSSProperties,
  
  passwordToggle: {
    position: 'absolute',
    right: '12px',
    top: '50%',
    transform: 'translateY(-50%)',
    background: 'none',
    border: 'none',
    color: '#666',
    cursor: 'pointer',
    padding: '4px',
    borderRadius: '4px',
  } as React.CSSProperties,
  
  errorMessage: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    color: '#e74c3c',
    fontSize: '14px',
    marginTop: '6px',
  } as React.CSSProperties,
  
  generalError: {
    background: '#fdf2f2',
    border: '1px solid #fecaca',
    borderRadius: '6px',
    padding: '12px',
    marginBottom: '20px',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    color: '#e74c3c',
    fontSize: '14px',
  } as React.CSSProperties,
  
  successMessage: {
    background: '#f0f9f4',
    border: '1px solid #bbf7d0',
    borderRadius: '6px',
    padding: '12px',
    marginBottom: '20px',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    color: '#16a34a',
    fontSize: '14px',
  } as React.CSSProperties,
  
  submitButton: {
    width: '100%',
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    color: 'white',
    border: 'none',
    padding: '14px 20px',
    borderRadius: '8px',
    fontSize: '16px',
    fontWeight: '600',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
  } as React.CSSProperties,
  
  submitButtonDisabled: {
    opacity: 0.7,
    cursor: 'not-allowed',
  } as React.CSSProperties,
  
  loadingSpinner: {
    width: '16px',
    height: '16px',
    border: '2px solid transparent',
    borderTop: '2px solid currentColor',
    borderRadius: '50%',
    animation: 'spin 1s linear infinite',
  } as React.CSSProperties,
  
  formFooter: {
    marginTop: '24px',
    textAlign: 'center',
  } as React.CSSProperties,
  
  linkButton: {
    background: 'none',
    border: 'none',
    color: '#667eea',
    cursor: 'pointer',
    fontSize: '14px',
    textDecoration: 'none',
  } as React.CSSProperties,
  
  switchForm: {
    color: '#666',
    fontSize: '14px',
    marginTop: '16px',
  } as React.CSSProperties,
  
  verificationContainer: {
    textAlign: 'center',
  } as React.CSSProperties,
  
  verificationIcon: {
    width: '64px',
    height: '64px',
    margin: '0 auto 24px',
    background: '#f3f4f6',
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#667eea',
  } as React.CSSProperties,
  
  verificationText: {
    color: '#666',
    lineHeight: '1.5',
    marginBottom: '24px',
  } as React.CSSProperties,
  
  resendButton: {
    background: 'none',
    border: '1px solid #e1e5e9',
    color: '#667eea',
    padding: '8px 16px',
    borderRadius: '6px',
    fontSize: '14px',
    cursor: 'pointer',
    marginTop: '16px',
  } as React.CSSProperties,
};

export const RegisterForm: React.FC<RegisterFormProps> = ({ onSuccess, onSwitchToLogin }) => {
  const { register, isLoading } = useAuth();
  
  const [registrationStep, setRegistrationStep] = useState<RegistrationStep>({ step: 'register' });
  const [formData, setFormData] = useState<RegisterRequest>({
    username: '',
    email: '',
    password: '',
    confirm_password: '',
  });
  
  const [errors, setErrors] = useState<FormErrors>({});
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // Email validation helper
  const isValidEmail = (email: string): boolean => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  // Password strength validation
  const validatePasswordStrength = (password: string): string | null => {
    if (password.length < 8) {
      return 'Password must be at least 8 characters long';
    }
    if (!/(?=.*[a-z])/.test(password)) {
      return 'Password must contain at least one lowercase letter';
    }
    if (!/(?=.*[A-Z])/.test(password)) {
      return 'Password must contain at least one uppercase letter';
    }
    if (!/(?=.*\d)/.test(password)) {
      return 'Password must contain at least one number';
    }
    return null;
  };

  // Form validation
  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};

    // Username validation
    if (!formData.username.trim()) {
      newErrors.username = 'Username is required';
    } else if (formData.username.length < 3) {
      newErrors.username = 'Username must be at least 3 characters';
    } else if (formData.username.length > 30) {
      newErrors.username = 'Username must be less than 30 characters';
    } else if (!/^[a-zA-Z0-9_-]+$/.test(formData.username)) {
      newErrors.username = 'Username can only contain letters, numbers, hyphens, and underscores';
    }

    // Email validation
    if (!formData.email.trim()) {
      newErrors.email = 'Email is required';
    } else if (!isValidEmail(formData.email)) {
      newErrors.email = 'Please enter a valid email address';
    }

    // Password validation
    if (!formData.password) {
      newErrors.password = 'Password is required';
    } else {
      const passwordError = validatePasswordStrength(formData.password);
      if (passwordError) {
        newErrors.password = passwordError;
      }
    }

    // Confirm password validation
    if (!formData.confirm_password) {
      newErrors.confirm_password = 'Please confirm your password';
    } else if (formData.password !== formData.confirm_password) {
      newErrors.confirm_password = 'Passwords do not match';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Handle input changes
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    
    // Clear field-specific errors when user types
    if (errors[name as keyof FormErrors]) {
      setErrors(prev => ({ ...prev, [name]: undefined }));
    }
    
    // Clear general errors when user makes changes
    if (errors.general) {
      setErrors(prev => ({ ...prev, general: undefined }));
    }
  };

  // Handle form submission
  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    try {
      const result = await register(formData);
      
      if (result.success) {
        // Move to email verification step
        setRegistrationStep({ 
          step: 'verify-email', 
          email: formData.email 
        });
        setErrors({});
        
        // Call onSuccess callback if provided
        onSuccess?.();
      } else {
        setErrors({ general: result.error || 'Registration failed' });
      }
    } catch (error) {
      console.error('Registration error:', error);
      setErrors({ general: 'An unexpected error occurred. Please try again.' });
    }
  };

  // Handle resend verification email
  const handleResendVerification = async () => {
    try {
      // TODO: Implement resend verification email API call
      // For now, show a success message
      setErrors({});
      // Could show a temporary success message here
    } catch (error) {
      console.error('Resend verification error:', error);
      setErrors({ general: 'Failed to resend verification email. Please try again.' });
    }
  };

  // Render email verification step
  const renderEmailVerification = () => (
    <div style={styles.verificationContainer}>
      <div style={styles.verificationIcon}>
        <svg width="32" height="32" viewBox="0 0 24 24" fill="currentColor">
          <path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/>
        </svg>
      </div>
      
      <h2 style={styles.title}>Check Your Email</h2>
      <div style={styles.verificationText}>
        <p>We've sent a verification link to:</p>
        <strong>{registrationStep.email}</strong>
        <p style={{ marginTop: '16px' }}>
          Click the link in the email to verify your account and complete registration.
        </p>
      </div>
      
      {errors.general && (
        <div style={styles.generalError} role="alert">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
            <path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z"/>
            <path d="M7.002 11a1 1 0 1 1 2 0 1 1 0 0 1-2 0zM7.1 4.995a.905.905 0 1 1 1.8 0l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 4.995z"/>
          </svg>
          {errors.general}
        </div>
      )}
      
      <button
        type="button"
        style={styles.resendButton}
        onClick={handleResendVerification}
        disabled={isLoading}
        className="resend-button"
      >
        Didn't receive the email? Resend
      </button>
      
      <div style={styles.formFooter}>
        <button
          type="button"
          className="link-button"
          style={styles.linkButton}
          onClick={onSwitchToLogin}
        >
          ← Back to sign in
        </button>
      </div>
    </div>
  );

  // Render registration form
  const renderRegistrationForm = () => (
    <>
      <h2 style={styles.title}>Create Account</h2>
      <p style={styles.subtitle}>Join us and start your adventure!</p>
      
      <form onSubmit={handleSubmit} noValidate>
        {/* General Error Display */}
        {errors.general && (
          <div style={styles.generalError} role="alert">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z"/>
              <path d="M7.002 11a1 1 0 1 1 2 0 1 1 0 0 1-2 0zM7.1 4.995a.905.905 0 1 1 1.8 0l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 4.995z"/>
            </svg>
            {errors.general}
          </div>
        )}

        {/* Username Field */}
        <div style={styles.formGroup}>
          <label htmlFor="username" style={styles.label}>
            Username
          </label>
          <input
            type="text"
            id="username"
            name="username"
            value={formData.username}
            onChange={handleInputChange}
            className={`form-input ${errors.username ? 'error' : ''}`}
            style={{
              ...styles.input,
              ...(errors.username ? styles.inputError : {}),
            }}
            placeholder="Choose a username"
            disabled={isLoading}
            autoComplete="username"
            aria-describedby={errors.username ? 'username-error' : undefined}
            aria-invalid={!!errors.username}
          />
          {errors.username && (
            <div id="username-error" style={styles.errorMessage} role="alert">
              {errors.username}
            </div>
          )}
        </div>

        {/* Email Field */}
        <div style={styles.formGroup}>
          <label htmlFor="email" style={styles.label}>
            Email Address
          </label>
          <input
            type="email"
            id="email"
            name="email"
            value={formData.email}
            onChange={handleInputChange}
            className={`form-input ${errors.email ? 'error' : ''}`}
            style={{
              ...styles.input,
              ...(errors.email ? styles.inputError : {}),
            }}
            placeholder="Enter your email address"
            disabled={isLoading}
            autoComplete="email"
            aria-describedby={errors.email ? 'email-error' : undefined}
            aria-invalid={!!errors.email}
          />
          {errors.email && (
            <div id="email-error" style={styles.errorMessage} role="alert">
              {errors.email}
            </div>
          )}
        </div>

        {/* Password Field */}
        <div style={styles.formGroup}>
          <label htmlFor="password" style={styles.label}>
            Password
          </label>
          <div style={styles.passwordContainer}>
            <input
              type={showPassword ? 'text' : 'password'}
              id="password"
              name="password"
              value={formData.password}
              onChange={handleInputChange}
              className={`form-input ${errors.password ? 'error' : ''}`}
              style={{
                ...styles.input,
                ...(errors.password ? styles.inputError : {}),
              }}
              placeholder="Create a strong password"
              disabled={isLoading}
              autoComplete="new-password"
              aria-describedby={errors.password ? 'password-error' : undefined}
              aria-invalid={!!errors.password}
            />
            <button
              type="button"
              style={styles.passwordToggle}
              onClick={() => setShowPassword(!showPassword)}
              disabled={isLoading}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              tabIndex={-1}
            >
              {showPassword ? (
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M13.359 11.238C15.06 9.72 16 8 16 8s-3-5.5-8-5.5a7.028 7.028 0 0 0-2.79.588l.77.771A5.944 5.944 0 0 1 8 3.5c2.12 0 3.879 1.168 5.168 2.457A13.134 13.134 0 0 1 14.828 8c-.058.087-.122.183-.195.288-.335.48-.83 1.12-1.465 1.755-.165.165-.337.328-.517.486l.708.709z"/>
                  <path d="M11.297 9.176a3.5 3.5 0 0 0-4.474-4.474l.823.823a2.5 2.5 0 0 1 2.829 2.829l.822.822zm-2.943 1.299.822.822a3.5 3.5 0 0 1-4.474-4.474l.823.823a2.5 2.5 0 0 0 2.829 2.829z"/>
                  <path d="M3.35 5.47c-.18.16-.353.322-.518.487A13.134 13.134 0 0 0 1.172 8l.195.288c.335.48.83 1.12 1.465 1.755C4.121 11.332 5.881 12.5 8 12.5c.716 0 1.39-.133 2.02-.36l.77.772A7.029 7.029 0 0 1 8 13.5C3 13.5 0 8 0 8s.939-1.721 2.641-3.238l.708.708zm10.296 8.884-12-12 .708-.708 12 12-.708.708z"/>
                </svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M16 8s-3-5.5-8-5.5S0 8 0 8s3 5.5 8 5.5S16 8 16 8zM1.173 8a13.133 13.133 0 0 1 1.66-2.043C4.12 4.668 5.88 3.5 8 3.5c2.12 0 3.879 1.168 5.168 2.457A13.133 13.133 0 0 1 14.828 8c-.058.087-.122.183-.195.288-.335.48-.83 1.12-1.465 1.755C11.879 11.332 10.119 12.5 8 12.5c-2.12 0-3.879-1.168-5.168-2.457A13.134 13.134 0 0 1 1.172 8z"/>
                  <path d="M8 5.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5zM4.5 8a3.5 3.5 0 1 1 7 0 3.5 3.5 0 0 1-7 0z"/>
                </svg>
              )}
            </button>
          </div>
          {errors.password && (
            <div id="password-error" style={styles.errorMessage} role="alert">
              {errors.password}
            </div>
          )}
        </div>

        {/* Confirm Password Field */}
        <div style={styles.formGroup}>
          <label htmlFor="confirm_password" style={styles.label}>
            Confirm Password
          </label>
          <div style={styles.passwordContainer}>
            <input
              type={showConfirmPassword ? 'text' : 'password'}
              id="confirm_password"
              name="confirm_password"
              value={formData.confirm_password}
              onChange={handleInputChange}
              className={`form-input ${errors.confirm_password ? 'error' : ''}`}
              style={{
                ...styles.input,
                ...(errors.confirm_password ? styles.inputError : {}),
              }}
              placeholder="Confirm your password"
              disabled={isLoading}
              autoComplete="new-password"
              aria-describedby={errors.confirm_password ? 'confirm-password-error' : undefined}
              aria-invalid={!!errors.confirm_password}
            />
            <button
              type="button"
              style={styles.passwordToggle}
              onClick={() => setShowConfirmPassword(!showConfirmPassword)}
              disabled={isLoading}
              aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
              tabIndex={-1}
            >
              {showConfirmPassword ? (
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M13.359 11.238C15.06 9.72 16 8 16 8s-3-5.5-8-5.5a7.028 7.028 0 0 0-2.79.588l.77.771A5.944 5.944 0 0 1 8 3.5c2.12 0 3.879 1.168 5.168 2.457A13.134 13.134 0 0 1 14.828 8c-.058.087-.122.183-.195.288-.335.48-.83 1.12-1.465 1.755-.165.165-.337.328-.517.486l.708.709z"/>
                  <path d="M11.297 9.176a3.5 3.5 0 0 0-4.474-4.474l.823.823a2.5 2.5 0 0 1 2.829 2.829l.822.822zm-2.943 1.299.822.822a3.5 3.5 0 0 1-4.474-4.474l.823.823a2.5 2.5 0 0 0 2.829 2.829z"/>
                  <path d="M3.35 5.47c-.18.16-.353.322-.518.487A13.134 13.134 0 0 0 1.172 8l.195.288c.335.48.83 1.12 1.465 1.755C4.121 11.332 5.881 12.5 8 12.5c.716 0 1.39-.133 2.02-.36l.77.772A7.029 7.029 0 0 1 8 13.5C3 13.5 0 8 0 8s.939-1.721 2.641-3.238l.708.708zm10.296 8.884-12-12 .708-.708 12 12-.708.708z"/>
                </svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M16 8s-3-5.5-8-5.5S0 8 0 8s3 5.5 8 5.5S16 8 16 8zM1.173 8a13.133 13.133 0 0 1 1.66-2.043C4.12 4.668 5.88 3.5 8 3.5c2.12 0 3.879 1.168 5.168 2.457A13.133 13.133 0 0 1 14.828 8c-.058.087-.122.183-.195.288-.335.48-.83 1.12-1.465 1.755C11.879 11.332 10.119 12.5 8 12.5c-2.12 0-3.879-1.168-5.168-2.457A13.134 13.134 0 0 1 1.172 8z"/>
                  <path d="M8 5.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5zM4.5 8a3.5 3.5 0 1 1 7 0 3.5 3.5 0 0 1-7 0z"/>
                </svg>
              )}
            </button>
          </div>
          {errors.confirm_password && (
            <div id="confirm-password-error" style={styles.errorMessage} role="alert">
              {errors.confirm_password}
            </div>
          )}
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          className="submit-button"
          style={{
            ...styles.submitButton,
            ...(isLoading ? styles.submitButtonDisabled : {}),
          }}
          disabled={isLoading}
          aria-describedby={isLoading ? 'loading-message' : undefined}
        >
          {isLoading ? (
            <>
              <div style={styles.loadingSpinner} aria-hidden="true"></div>
              <span id="loading-message">Creating account...</span>
            </>
          ) : (
            'Create Account'
          )}
        </button>
      </form>

      {/* Additional Actions */}
      <div style={styles.formFooter}>
        {onSwitchToLogin && (
          <div style={styles.switchForm}>
            <span>Already have an account? </span>
            <button
              type="button"
              className="link-button"
              style={styles.linkButton}
              onClick={onSwitchToLogin}
            >
              Sign in
            </button>
          </div>
        )}
      </div>
    </>
  );

  return (
    <>
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        
        .form-input:focus {
          outline: none !important;
          border-color: #667eea !important;
          box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
        }
        
        .form-input.error:focus {
          border-color: #e74c3c !important;
          box-shadow: 0 0 0 3px rgba(231, 76, 60, 0.1) !important;
        }
        
        .submit-button:hover:not(:disabled) {
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
        }
        
        .link-button:hover {
          color: #5a6fd8;
          text-decoration: underline;
        }
        
        .resend-button:hover:not(:disabled) {
          background-color: #f8fafc;
          border-color: #667eea;
        }
      `}</style>
      
      <div style={styles.container}>
        <div style={styles.form}>
          {registrationStep.step === 'register' && renderRegistrationForm()}
          {registrationStep.step === 'verify-email' && renderEmailVerification()}
        </div>
      </div>
    </>
  );
}; 