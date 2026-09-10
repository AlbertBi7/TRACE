/**
 * TRACE — Auth Context
 * Manages JWT tokens, user state, login/logout, and auto-refresh.
 */

import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import api from '../lib/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Check for existing session on mount
  useEffect(() => {
    const token = localStorage.getItem('trace_access_token');
    if (token) {
      api.get('/api/auth/me')
        .then(({ data }) => setUser(data))
        .catch(() => {
          localStorage.removeItem('trace_access_token');
          localStorage.removeItem('trace_refresh_token');
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = useCallback(async (email, password) => {
    const { data } = await api.post('/api/auth/login', { email, password });
    localStorage.setItem('trace_access_token', data.access_token);
    localStorage.setItem('trace_refresh_token', data.refresh_token);
    setUser(data.user);
    return data.user;
  }, []);

  const logout = useCallback(async () => {
    const refreshToken = localStorage.getItem('trace_refresh_token');
    try {
      if (refreshToken) {
        await api.post('/api/auth/logout', { refresh_token: refreshToken });
      }
    } catch {
      // Silently fail — we're logging out anyway
    }
    localStorage.removeItem('trace_access_token');
    localStorage.removeItem('trace_refresh_token');
    setUser(null);
  }, []);

  const isAdmin = user?.role === 'admin';
  const isInvestigator = user?.role === 'investigator';

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, isAdmin, isInvestigator }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
