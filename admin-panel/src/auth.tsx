import { createContext, useContext, useState, type ReactNode } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { api, getToken } from './api';

interface AuthCtx {
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTok] = useState<string | null>(getToken());
  const navigate = useNavigate();
  const login = async (email: string, password: string) => {
    const t = await api.login(email, password);
    setTok(t);
    navigate('/');
  };
  const logout = () => {
    api.logout();
    setTok(null);
    navigate('/login');
  };
  return <Ctx.Provider value={{ token, login, logout }}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useAuth outside provider');
  return ctx;
}

export function RequireStaff({ children }: { children: ReactNode }) {
  const { token } = useAuth();
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
