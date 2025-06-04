import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requireAuth?: boolean;
  redirectTo?: string;
}

/**
 * ProtectedRoute component that guards routes based on authentication status.
 * 
 * @param children - The component(s) to render if access is allowed
 * @param requireAuth - Whether authentication is required (default: true)
 * @param redirectTo - Where to redirect if access is denied (default: '/login')
 */
export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ 
  children, 
  requireAuth = true,
  redirectTo = '/login'
}) => {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  // Show loading indicator while authentication status is being determined
  if (isLoading) {
    return (
      <div style={loadingStyles.container}>
        <div style={loadingStyles.spinner}></div>
        <p style={loadingStyles.text}>Loading...</p>
      </div>
    );
  }

  // If authentication is required but user is not authenticated, redirect to login
  if (requireAuth && !isAuthenticated) {
    // Save the current location to redirect back after login
    return <Navigate to={redirectTo} state={{ from: location }} replace />;
  }

  // If authentication is not required but user is authenticated, 
  // and they're trying to access auth pages, redirect to home
  if (!requireAuth && isAuthenticated && (
    location.pathname === '/login' || 
    location.pathname === '/register'
  )) {
    // Get the original destination from location state, or default to home
    const from = location.state?.from?.pathname || '/';
    return <Navigate to={from} replace />;
  }

  // Render the protected content
  return <>{children}</>;
};

// Alternative component for routes that should only be accessible to non-authenticated users
export const PublicOnlyRoute: React.FC<{ children: React.ReactNode; redirectTo?: string }> = ({ 
  children, 
  redirectTo = '/' 
}) => {
  return (
    <ProtectedRoute requireAuth={false} redirectTo={redirectTo}>
      {children}
    </ProtectedRoute>
  );
};

// Loading styles
const loadingStyles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '100vh',
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  } as React.CSSProperties,
  
  spinner: {
    width: '40px',
    height: '40px',
    border: '4px solid rgba(255, 255, 255, 0.3)',
    borderTop: '4px solid white',
    borderRadius: '50%',
    animation: 'spin 1s linear infinite',
    marginBottom: '16px',
  } as React.CSSProperties,
  
  text: {
    color: 'white',
    fontSize: '16px',
    fontWeight: '500',
  } as React.CSSProperties,
};

// Add CSS animation for spinner
const style = document.createElement('style');
style.textContent = `
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
`;
document.head.appendChild(style); 