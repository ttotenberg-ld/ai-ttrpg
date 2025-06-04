import React, { createContext, useContext, useReducer, useEffect } from 'react';
import type { ReactNode } from 'react';
import type { AuthState, UserProfile, TokenResponse } from '../types/api';

// Auth Actions
type AuthAction =
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'LOGIN_SUCCESS'; payload: { user: UserProfile; accessToken: string; refreshToken: string } }
  | { type: 'LOGOUT' }
  | { type: 'TOKEN_REFRESH_SUCCESS'; payload: { accessToken: string; refreshToken: string } }
  | { type: 'UPDATE_USER_PROFILE'; payload: UserProfile };

// Auth Context Type
interface AuthContextType extends AuthState {
  login: (accessToken: string, refreshToken: string, user: UserProfile) => void;
  logout: () => void;
  refreshAuthToken: () => Promise<boolean>;
  updateUserProfile: (user: UserProfile) => void;
  setLoading: (loading: boolean) => void;
}

// Initial State
const initialState: AuthState = {
  isAuthenticated: false,
  isLoading: true,
  user: null,
  accessToken: null,
  refreshToken: null,
};

// Auth Reducer
const authReducer = (state: AuthState, action: AuthAction): AuthState => {
  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    case 'LOGIN_SUCCESS':
      return {
        ...state,
        isAuthenticated: true,
        isLoading: false,
        user: action.payload.user,
        accessToken: action.payload.accessToken,
        refreshToken: action.payload.refreshToken,
      };
    case 'LOGOUT':
      return {
        ...initialState,
        isLoading: false,
      };
    case 'TOKEN_REFRESH_SUCCESS':
      return {
        ...state,
        accessToken: action.payload.accessToken,
        refreshToken: action.payload.refreshToken,
      };
    case 'UPDATE_USER_PROFILE':
      return {
        ...state,
        user: action.payload,
      };
    default:
      return state;
  }
};

// Create Context
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Storage Keys
const ACCESS_TOKEN_KEY = 'auth_access_token';
const REFRESH_TOKEN_KEY = 'auth_refresh_token';
const USER_PROFILE_KEY = 'auth_user_profile';

// Auth Provider Component
export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [state, dispatch] = useReducer(authReducer, initialState);

  // Initialize auth state from localStorage on app start
  useEffect(() => {
    const initializeAuth = () => {
      try {
        const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
        const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
        const userProfile = localStorage.getItem(USER_PROFILE_KEY);

        if (accessToken && refreshToken && userProfile) {
          const user = JSON.parse(userProfile) as UserProfile;
          dispatch({
            type: 'LOGIN_SUCCESS',
            payload: { user, accessToken, refreshToken },
          });
        } else {
          dispatch({ type: 'SET_LOADING', payload: false });
        }
      } catch (error) {
        console.error('Error initializing auth state:', error);
        // Clear potentially corrupted data
        localStorage.removeItem(ACCESS_TOKEN_KEY);
        localStorage.removeItem(REFRESH_TOKEN_KEY);
        localStorage.removeItem(USER_PROFILE_KEY);
        dispatch({ type: 'SET_LOADING', payload: false });
      }
    };

    initializeAuth();
  }, []);

  // Login function
  const login = (accessToken: string, refreshToken: string, user: UserProfile) => {
    try {
      localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
      localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
      localStorage.setItem(USER_PROFILE_KEY, JSON.stringify(user));

      dispatch({
        type: 'LOGIN_SUCCESS',
        payload: { user, accessToken, refreshToken },
      });
    } catch (error) {
      console.error('Error storing auth data:', error);
      throw new Error('Failed to store authentication data');
    }
  };

  // Logout function
  const logout = () => {
    try {
      localStorage.removeItem(ACCESS_TOKEN_KEY);
      localStorage.removeItem(REFRESH_TOKEN_KEY);
      localStorage.removeItem(USER_PROFILE_KEY);

      dispatch({ type: 'LOGOUT' });
    } catch (error) {
      console.error('Error during logout:', error);
    }
  };

  // Refresh token function
  const refreshAuthToken = async (): Promise<boolean> => {
    if (!state.refreshToken) {
      logout();
      return false;
    }

    try {
      const response = await fetch('/api/auth/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh_token: state.refreshToken }),
      });

      if (!response.ok) {
        logout();
        return false;
      }

      const tokenData: TokenResponse = await response.json();
      
      localStorage.setItem(ACCESS_TOKEN_KEY, tokenData.access_token);
      localStorage.setItem(REFRESH_TOKEN_KEY, tokenData.refresh_token);

      dispatch({
        type: 'TOKEN_REFRESH_SUCCESS',
        payload: {
          accessToken: tokenData.access_token,
          refreshToken: tokenData.refresh_token,
        },
      });

      return true;
    } catch (error) {
      console.error('Error refreshing token:', error);
      logout();
      return false;
    }
  };

  // Update user profile function
  const updateUserProfile = (user: UserProfile) => {
    try {
      localStorage.setItem(USER_PROFILE_KEY, JSON.stringify(user));
      dispatch({ type: 'UPDATE_USER_PROFILE', payload: user });
    } catch (error) {
      console.error('Error updating user profile:', error);
      throw new Error('Failed to update user profile');
    }
  };

  // Set loading function
  const setLoading = (loading: boolean) => {
    dispatch({ type: 'SET_LOADING', payload: loading });
  };

  const contextValue: AuthContextType = {
    ...state,
    login,
    logout,
    refreshAuthToken,
    updateUserProfile,
    setLoading,
  };

  return <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>;
};

// Custom hook to use auth context
export const useAuthContext = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuthContext must be used within an AuthProvider');
  }
  return context;
}; 