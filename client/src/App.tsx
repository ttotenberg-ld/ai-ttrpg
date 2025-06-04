import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { ProtectedRoute, PublicOnlyRoute } from './components/auth/ProtectedRoute';
import { AuthLayout } from './components/auth/AuthLayout';
import { Header } from './components/layout/Header';
import GameApp from './components/GameApp';
import './App.css';

function App() {
  return (
    <AuthProvider>
      <Router>
        <div className="App">
          <Header />
          <main>
            <Routes>
              {/* Public routes - only accessible when not authenticated */}
              <Route 
                path="/login" 
                element={
                  <PublicOnlyRoute>
                    <AuthLayout initialMode="login" />
                  </PublicOnlyRoute>
                } 
              />
              <Route 
                path="/register" 
                element={
                  <PublicOnlyRoute>
                    <AuthLayout initialMode="register" />
                  </PublicOnlyRoute>
                } 
              />

              {/* Protected routes - require authentication */}
              <Route 
                path="/" 
                element={
                  <ProtectedRoute>
                    <GameApp />
                  </ProtectedRoute>
                } 
              />
              <Route 
                path="/characters" 
                element={
                  <ProtectedRoute>
                    <GameApp />
                  </ProtectedRoute>
                } 
              />
              <Route 
                path="/adventure/:adventureId?" 
                element={
                  <ProtectedRoute>
                    <GameApp />
                  </ProtectedRoute>
                } 
              />

              {/* Catch all route - redirect to home */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </Router>
    </AuthProvider>
  );
}

export default App;
