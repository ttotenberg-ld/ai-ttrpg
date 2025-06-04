import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { LoginForm } from './LoginForm';
import { RegisterForm } from './RegisterForm';

type AuthMode = 'login' | 'register';

interface AuthLayoutProps {
  initialMode?: AuthMode;
}

/**
 * AuthLayout component that handles authentication flow.
 * Manages switching between login and register forms.
 */
export const AuthLayout: React.FC<AuthLayoutProps> = ({ initialMode = 'login' }) => {
  const [authMode, setAuthMode] = useState<AuthMode>(initialMode);
  const navigate = useNavigate();
  const location = useLocation();

  // Get the intended destination from location state
  const from = location.state?.from?.pathname || '/';

  const handleAuthSuccess = () => {
    // Redirect to the originally intended page after successful authentication
    navigate(from, { replace: true });
  };

  const handleSwitchToRegister = () => {
    setAuthMode('register');
  };

  const handleSwitchToLogin = () => {
    setAuthMode('login');
  };

  return (
    <>
      {authMode === 'login' ? (
        <LoginForm
          onSuccess={handleAuthSuccess}
          onSwitchToRegister={handleSwitchToRegister}
        />
      ) : (
        <RegisterForm
          onSuccess={handleAuthSuccess}
          onSwitchToLogin={handleSwitchToLogin}
        />
      )}
    </>
  );
}; 