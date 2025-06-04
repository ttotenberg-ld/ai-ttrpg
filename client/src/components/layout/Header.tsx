import React from 'react';
import { useAuth } from '../../hooks/useAuth';

interface HeaderProps {
  title?: string;
}

export const Header: React.FC<HeaderProps> = ({ title = 'AI TTRPG' }) => {
  const { user, logout, isAuthenticated } = useAuth();

  const handleLogout = async () => {
    try {
      await logout();
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  return (
    <header style={styles.header}>
      <div style={styles.container}>
        <h1 style={styles.title}>{title}</h1>
        
        {isAuthenticated && user && (
          <div style={styles.userSection}>
            <span style={styles.username}>Welcome, {user.username}!</span>
            <button 
              onClick={handleLogout}
              style={styles.logoutButton}
              className="logout-button"
            >
              Sign Out
            </button>
          </div>
        )}
      </div>
      
      <style>{`
        .logout-button:hover {
          background-color: rgba(255, 255, 255, 0.1) !important;
          transform: translateY(-1px);
        }
      `}</style>
    </header>
  );
};

const styles = {
  header: {
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    color: 'white',
    padding: '1rem 0',
    boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)',
  } as React.CSSProperties,
  
  container: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    maxWidth: '1200px',
    margin: '0 auto',
    padding: '0 1rem',
  } as React.CSSProperties,
  
  title: {
    margin: 0,
    fontSize: '1.8rem',
    fontWeight: '600',
  } as React.CSSProperties,
  
  userSection: {
    display: 'flex',
    alignItems: 'center',
    gap: '1rem',
  } as React.CSSProperties,
  
  username: {
    fontSize: '0.9rem',
    opacity: 0.9,
  } as React.CSSProperties,
  
  logoutButton: {
    background: 'rgba(255, 255, 255, 0.1)',
    border: '1px solid rgba(255, 255, 255, 0.3)',
    color: 'white',
    padding: '0.5rem 1rem',
    borderRadius: '6px',
    fontSize: '0.85rem',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
  } as React.CSSProperties,
}; 