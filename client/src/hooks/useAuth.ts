import { useCallback } from 'react';
import { useAuthContext } from '../contexts/AuthContext';
import type { 
  LoginRequest, 
  RegisterRequest, 
  UserProfile, 
  UserProfileUpdate, 
  PasswordResetConfirm,
  TokenResponse,
  APIError 
} from '../types/api';

interface AuthOperations {
  // State
  isAuthenticated: boolean;
  isLoading: boolean;
  user: UserProfile | null;
  accessToken: string | null;
  
  // Authentication Operations
  login: (credentials: LoginRequest) => Promise<{ success: boolean; error?: string }>;
  register: (userData: RegisterRequest) => Promise<{ success: boolean; error?: string }>;
  logout: () => Promise<void>;
  
  // Profile Management
  getUserProfile: () => Promise<{ success: boolean; user?: UserProfile; error?: string }>;
  updateUserProfile: (updates: UserProfileUpdate) => Promise<{ success: boolean; user?: UserProfile; error?: string }>;
  
  // Password Management
  requestPasswordReset: (email: string) => Promise<{ success: boolean; error?: string }>;
  confirmPasswordReset: (resetData: PasswordResetConfirm) => Promise<{ success: boolean; error?: string }>;
  
  // Token Management
  refreshToken: () => Promise<boolean>;
}

export const useAuth = (): AuthOperations => {
  const authContext = useAuthContext();

  // Login function
  const login = useCallback(async (credentials: LoginRequest): Promise<{ success: boolean; error?: string }> => {
    try {
      authContext.setLoading(true);

      const formData = new FormData();
      formData.append('username', credentials.username);
      formData.append('password', credentials.password);

      const response = await fetch('/api/auth/login', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData: APIError = await response.json();
        const errorMessage = typeof errorData.detail === 'string' 
          ? errorData.detail 
          : 'Login failed';
        return { success: false, error: errorMessage };
      }

      const tokenData: TokenResponse = await response.json();
      
      // Get user profile after successful login
      const profileResponse = await fetch('/api/users/profile', {
        headers: {
          'Authorization': `Bearer ${tokenData.access_token}`,
        },
      });

      if (!profileResponse.ok) {
        return { success: false, error: 'Failed to retrieve user profile' };
      }

      const userProfile: UserProfile = await profileResponse.json();
      
      // Store auth data in context
      authContext.login(tokenData.access_token, tokenData.refresh_token, userProfile);
      
      return { success: true };
    } catch (error) {
      console.error('Login error:', error);
      return { success: false, error: 'Network error occurred' };
    } finally {
      authContext.setLoading(false);
    }
  }, [authContext]);

  // Register function
  const register = useCallback(async (userData: RegisterRequest): Promise<{ success: boolean; error?: string }> => {
    try {
      authContext.setLoading(true);

      if (userData.password !== userData.confirm_password) {
        return { success: false, error: 'Passwords do not match' };
      }

      const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: userData.username,
          email: userData.email,
          password: userData.password,
        }),
      });

      if (!response.ok) {
        const errorData: APIError = await response.json();
        const errorMessage = typeof errorData.detail === 'string' 
          ? errorData.detail 
          : 'Registration failed';
        return { success: false, error: errorMessage };
      }

      return { success: true };
    } catch (error) {
      console.error('Registration error:', error);
      return { success: false, error: 'Network error occurred' };
    } finally {
      authContext.setLoading(false);
    }
  }, [authContext]);

  // Logout function
  const logout = useCallback(async (): Promise<void> => {
    try {
      // Call logout endpoint to blacklist refresh token
      if (authContext.refreshToken) {
        await fetch('/api/auth/logout', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authContext.accessToken}`,
          },
          body: JSON.stringify({ refresh_token: authContext.refreshToken }),
        });
      }
    } catch (error) {
      console.error('Logout API error:', error);
      // Continue with local logout even if API call fails
    } finally {
      authContext.logout();
    }
  }, [authContext]);

  // Get user profile function
  const getUserProfile = useCallback(async (): Promise<{ success: boolean; user?: UserProfile; error?: string }> => {
    try {
      if (!authContext.accessToken) {
        return { success: false, error: 'No access token available' };
      }

      const response = await fetch('/api/users/profile', {
        headers: {
          'Authorization': `Bearer ${authContext.accessToken}`,
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          // Try to refresh token
          const refreshSuccess = await authContext.refreshAuthToken();
          if (refreshSuccess) {
            // Retry with new token
            const retryResponse = await fetch('/api/users/profile', {
              headers: {
                'Authorization': `Bearer ${authContext.accessToken}`,
              },
            });
            
            if (retryResponse.ok) {
              const userProfile: UserProfile = await retryResponse.json();
              authContext.updateUserProfile(userProfile);
              return { success: true, user: userProfile };
            }
          }
          // If refresh failed or retry failed, logout
          authContext.logout();
          return { success: false, error: 'Session expired' };
        }

        const errorData: APIError = await response.json();
        const errorMessage = typeof errorData.detail === 'string' 
          ? errorData.detail 
          : 'Failed to get user profile';
        return { success: false, error: errorMessage };
      }

      const userProfile: UserProfile = await response.json();
      authContext.updateUserProfile(userProfile);
      return { success: true, user: userProfile };
    } catch (error) {
      console.error('Get user profile error:', error);
      return { success: false, error: 'Network error occurred' };
    }
  }, [authContext]);

  // Update user profile function
  const updateUserProfile = useCallback(async (updates: UserProfileUpdate): Promise<{ success: boolean; user?: UserProfile; error?: string }> => {
    try {
      if (!authContext.accessToken) {
        return { success: false, error: 'No access token available' };
      }

      const response = await fetch('/api/users/profile', {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authContext.accessToken}`,
        },
        body: JSON.stringify(updates),
      });

      if (!response.ok) {
        if (response.status === 401) {
          // Try to refresh token
          const refreshSuccess = await authContext.refreshAuthToken();
          if (refreshSuccess) {
            // Retry with new token
            const retryResponse = await fetch('/api/users/profile', {
              method: 'PATCH',
              headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authContext.accessToken}`,
              },
              body: JSON.stringify(updates),
            });
            
            if (retryResponse.ok) {
              const updatedProfile: UserProfile = await retryResponse.json();
              authContext.updateUserProfile(updatedProfile);
              return { success: true, user: updatedProfile };
            }
          }
          // If refresh failed or retry failed, logout
          authContext.logout();
          return { success: false, error: 'Session expired' };
        }

        const errorData: APIError = await response.json();
        const errorMessage = typeof errorData.detail === 'string' 
          ? errorData.detail 
          : 'Failed to update user profile';
        return { success: false, error: errorMessage };
      }

      const updatedProfile: UserProfile = await response.json();
      authContext.updateUserProfile(updatedProfile);
      return { success: true, user: updatedProfile };
    } catch (error) {
      console.error('Update user profile error:', error);
      return { success: false, error: 'Network error occurred' };
    }
  }, [authContext]);

  // Request password reset function
  const requestPasswordReset = useCallback(async (email: string): Promise<{ success: boolean; error?: string }> => {
    try {
      const response = await fetch('/api/auth/forgot-password', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email }),
      });

      if (!response.ok) {
        const errorData: APIError = await response.json();
        const errorMessage = typeof errorData.detail === 'string' 
          ? errorData.detail 
          : 'Failed to request password reset';
        return { success: false, error: errorMessage };
      }

      return { success: true };
    } catch (error) {
      console.error('Password reset request error:', error);
      return { success: false, error: 'Network error occurred' };
    }
  }, []);

  // Confirm password reset function
  const confirmPasswordReset = useCallback(async (resetData: PasswordResetConfirm): Promise<{ success: boolean; error?: string }> => {
    try {
      if (resetData.new_password !== resetData.confirm_password) {
        return { success: false, error: 'Passwords do not match' };
      }

      const response = await fetch('/api/auth/reset-password', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          token: resetData.token,
          new_password: resetData.new_password,
        }),
      });

      if (!response.ok) {
        const errorData: APIError = await response.json();
        const errorMessage = typeof errorData.detail === 'string' 
          ? errorData.detail 
          : 'Failed to reset password';
        return { success: false, error: errorMessage };
      }

      return { success: true };
    } catch (error) {
      console.error('Password reset confirmation error:', error);
      return { success: false, error: 'Network error occurred' };
    }
  }, []);

  // Refresh token function
  const refreshToken = useCallback(async (): Promise<boolean> => {
    return await authContext.refreshAuthToken();
  }, [authContext]);

  return {
    // State
    isAuthenticated: authContext.isAuthenticated,
    isLoading: authContext.isLoading,
    user: authContext.user,
    accessToken: authContext.accessToken,
    
    // Operations
    login,
    register,
    logout,
    getUserProfile,
    updateUserProfile,
    requestPasswordReset,
    confirmPasswordReset,
    refreshToken,
  };
}; 