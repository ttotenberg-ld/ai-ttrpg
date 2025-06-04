import type { TokenResponse, APIError } from '../types/api';

// API Configuration
const API_BASE_URL = '/api';

// Token Storage Keys
const ACCESS_TOKEN_KEY = 'auth_access_token';
const REFRESH_TOKEN_KEY = 'auth_refresh_token';

// Response Types
interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
  status?: number;
}

interface RequestConfig extends RequestInit {
  skipAuth?: boolean;
  skipRefresh?: boolean;
}

class ApiService {
  private isRefreshing: boolean = false;
  private refreshSubscribers: Array<(token: string) => void> = [];

  // Get stored tokens
  private getAccessToken(): string | null {
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  }

  private getRefreshToken(): string | null {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  }

  // Store tokens
  private setTokens(accessToken: string, refreshToken: string): void {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  }

  // Clear tokens
  private clearTokens(): void {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  }

  // Add subscriber for token refresh
  private addRefreshSubscriber(callback: (token: string) => void): void {
    this.refreshSubscribers.push(callback);
  }

  // Notify all subscribers when token is refreshed
  private notifyRefreshSubscribers(token: string): void {
    this.refreshSubscribers.forEach(callback => callback(token));
    this.refreshSubscribers = [];
  }

  // Refresh access token
  private async refreshAccessToken(): Promise<string | null> {
    const refreshToken = this.getRefreshToken();
    
    if (!refreshToken) {
      return null;
    }

    if (this.isRefreshing) {
      // If already refreshing, wait for it to complete
      return new Promise((resolve) => {
        this.addRefreshSubscriber((token: string) => {
          resolve(token);
        });
      });
    }

    this.isRefreshing = true;

    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) {
        this.clearTokens();
        this.isRefreshing = false;
        return null;
      }

      const tokenData: TokenResponse = await response.json();
      this.setTokens(tokenData.access_token, tokenData.refresh_token);
      
      this.isRefreshing = false;
      this.notifyRefreshSubscribers(tokenData.access_token);
      
      return tokenData.access_token;
    } catch (error) {
      console.error('Token refresh failed:', error);
      this.clearTokens();
      this.isRefreshing = false;
      return null;
    }
  }

  // Make authenticated request
  private async makeRequest<T = unknown>(
    endpoint: string, 
    config: RequestConfig = {}
  ): Promise<ApiResponse<T>> {
    const { skipAuth = false, skipRefresh = false, ...requestConfig } = config;
    
    // Prepare headers
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...requestConfig.headers,
    };

    // Add authorization header if not skipping auth
    if (!skipAuth) {
      const accessToken = this.getAccessToken();
      if (accessToken) {
        (headers as Record<string, string>)['Authorization'] = `Bearer ${accessToken}`;
      }
    }

    // Make the request
    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...requestConfig,
        headers,
      });

      // Handle 401 Unauthorized
      if (response.status === 401 && !skipAuth && !skipRefresh) {
        // Try to refresh token
        const newToken = await this.refreshAccessToken();
        
        if (newToken) {
          // Retry the original request with new token
          const retryHeaders = {
            ...headers,
            'Authorization': `Bearer ${newToken}`,
          };
          
          const retryResponse = await fetch(`${API_BASE_URL}${endpoint}`, {
            ...requestConfig,
            headers: retryHeaders,
          });
          
          return this.handleResponse<T>(retryResponse);
        } else {
          // Refresh failed, user needs to login again
          return {
            success: false,
            error: 'Session expired. Please login again.',
            status: 401,
          };
        }
      }

      return this.handleResponse<T>(response);
    } catch (error) {
      console.error('API request failed:', error);
      return {
        success: false,
        error: 'Network error occurred',
      };
    }
  }

  // Handle response
  private async handleResponse<T>(response: Response): Promise<ApiResponse<T>> {
    try {
      if (response.ok) {
        // Handle successful response
        const contentType = response.headers.get('content-type');
        
        if (contentType && contentType.includes('application/json')) {
          const data = await response.json();
          return {
            success: true,
            data,
            status: response.status,
          };
        } else {
          // Non-JSON response (e.g., for endpoints that return plain text)
          return {
            success: true,
            status: response.status,
          };
        }
      } else {
        // Handle error response
        let errorMessage = `Request failed with status ${response.status}`;
        
        try {
          const errorData: APIError = await response.json();
          if (typeof errorData.detail === 'string') {
            errorMessage = errorData.detail;
          } else if (Array.isArray(errorData.detail)) {
            errorMessage = errorData.detail.map(err => err.msg).join(', ');
          }
        } catch {
          // If error response is not JSON, use status text
          errorMessage = response.statusText || errorMessage;
        }

        return {
          success: false,
          error: errorMessage,
          status: response.status,
        };
      }
    } catch (error) {
      console.error('Error handling response:', error);
      return {
        success: false,
        error: 'Failed to process server response',
        status: response.status,
      };
    }
  }

  // Public API methods
  
  // GET request
  async get<T = unknown>(endpoint: string, config?: RequestConfig): Promise<ApiResponse<T>> {
    return this.makeRequest<T>(endpoint, { ...config, method: 'GET' });
  }

  // POST request
  async post<T = unknown>(endpoint: string, data?: unknown, config?: RequestConfig): Promise<ApiResponse<T>> {
    return this.makeRequest<T>(endpoint, {
      ...config,
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  // PUT request
  async put<T = unknown>(endpoint: string, data?: unknown, config?: RequestConfig): Promise<ApiResponse<T>> {
    return this.makeRequest<T>(endpoint, {
      ...config,
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  // PATCH request
  async patch<T = unknown>(endpoint: string, data?: unknown, config?: RequestConfig): Promise<ApiResponse<T>> {
    return this.makeRequest<T>(endpoint, {
      ...config,
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  // DELETE request
  async delete<T = unknown>(endpoint: string, config?: RequestConfig): Promise<ApiResponse<T>> {
    return this.makeRequest<T>(endpoint, { ...config, method: 'DELETE' });
  }

  // Upload file (multipart/form-data)
  async upload<T = unknown>(endpoint: string, formData: FormData, config?: RequestConfig): Promise<ApiResponse<T>> {
    const { headers, ...restConfig } = config || {};
    
    // Don't set Content-Type header for FormData, let browser set it with boundary
    const uploadHeaders = { ...headers };
    if (uploadHeaders && 'Content-Type' in uploadHeaders) {
      delete uploadHeaders['Content-Type'];
    }

    return this.makeRequest<T>(endpoint, {
      ...restConfig,
      method: 'POST',
      body: formData,
      headers: uploadHeaders,
    });
  }

  // Form-encoded request (for OAuth2 login)
  async postForm<T = unknown>(endpoint: string, formData: FormData, config?: RequestConfig): Promise<ApiResponse<T>> {
    const { headers, ...restConfig } = config || {};
    
    return this.makeRequest<T>(endpoint, {
      ...restConfig,
      method: 'POST',
      body: formData,
      headers: {
        ...headers,
        // Remove Content-Type to let browser set it for FormData
      },
    });
  }

  // Check if user is authenticated
  isAuthenticated(): boolean {
    return !!this.getAccessToken();
  }

  // Get current access token
  getCurrentAccessToken(): string | null {
    return this.getAccessToken();
  }

  // Manual token refresh
  async refreshToken(): Promise<boolean> {
    const newToken = await this.refreshAccessToken();
    return !!newToken;
  }

  // Clear authentication
  clearAuth(): void {
    this.clearTokens();
  }
}

// Export singleton instance
export const apiService = new ApiService();

// Export types for use in components
export type { ApiResponse, RequestConfig }; 