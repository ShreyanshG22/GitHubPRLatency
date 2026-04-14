import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import axios from 'axios';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import ReviewDetailPage from './pages/ReviewDetailPage';
import SettingsPage from './pages/SettingsPage';
import TeamPage from './pages/TeamPage';
import './App.css';

const API = process.env.REACT_APP_BACKEND_URL;

// ─── Auth Context ───────────────────────────────────────────────────
const AuthContext = createContext(null);

export function useAuth() {
  return useContext(AuthContext);
}

// Axios instance with automatic token injection
export const api = axios.create({ baseURL: API });
api.interceptors.request.use(cfg => {
  const token = localStorage.getItem('token');
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

function AuthProvider({ children }) {
  const [user, setUser] = useState(null);      // null = checking
  const [checked, setChecked] = useState(false);

  const checkAuth = useCallback(async () => {
    try {
      const token = localStorage.getItem('token');
      if (!token) { setUser(false); setChecked(true); return; }
      const { data } = await api.get('/api/auth/me');
      setUser(data);
    } catch {
      localStorage.removeItem('token');
      setUser(false);
    } finally {
      setChecked(true);
    }
  }, []);

  useEffect(() => { checkAuth(); }, [checkAuth]);

  const login = async (email, password) => {
    const { data } = await api.post('/api/auth/login', { email, password });
    localStorage.setItem('token', data.token);
    setUser(data);
    return data;
  };

  const register = async (email, password, name) => {
    const { data } = await api.post('/api/auth/register', { email, password, name });
    localStorage.setItem('token', data.token);
    setUser(data);
    return data;
  };

  const logout = async () => {
    try { await api.post('/api/auth/logout'); } catch {}
    localStorage.removeItem('token');
    setUser(false);
  };

  if (!checked) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
        <span className="mono loading-pulse" style={{ color: 'var(--text-tertiary)', fontSize: '0.8rem', letterSpacing: '0.2em', textTransform: 'uppercase' }}>
          Initializing...
        </span>
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{ user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

function ProtectedRoute({ children }) {
  const { user } = useAuth();
  if (user === false) return <Navigate to="/login" replace />;
  return children;
}

function PublicRoute({ children }) {
  const { user } = useAuth();
  if (user && user !== false) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
          <Route path="/" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
          <Route path="/review/:reviewId" element={<ProtectedRoute><ReviewDetailPage /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
          <Route path="/team" element={<ProtectedRoute><TeamPage /></ProtectedRoute>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
