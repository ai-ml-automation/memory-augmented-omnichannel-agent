import { create } from 'zustand';
import { api } from '../api/axios';

export interface User {
  id: string;
  phone_hash: string;
  full_name?: string;
  role?: string;
  created_at: string;
  is_active: boolean;
  tenant_id: string;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (phone: string, password: string) => Promise<void>;
  register: (phone: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,

  login: async (phone: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      await api.post('/auth/login', { phone, password });
      const { data: user } = await api.get('/auth/me');
      set({ user, isAuthenticated: true, isLoading: false });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Login failed';
      set({ error: message, isLoading: false });
      throw error;
    }
  },

  register: async (phone: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      await api.post('/auth/register', { phone, password });
      await api.post('/auth/login', { phone, password });
      const { data: user } = await api.get('/auth/me');
      set({ user, isAuthenticated: true, isLoading: false });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Registration failed';
      set({ error: message, isLoading: false });
      throw error;
    }
  },

  logout: async () => {
    set({ isLoading: true, error: null });
    try {
      await api.post('/auth/logout');
      set({ user: null, isAuthenticated: false, isLoading: false });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Logout failed';
      set({ error: message, isLoading: false });
      throw error;
    }
  },

  checkAuth: async () => {
    set({ isLoading: true, error: null });
    try {
      const { data: user } = await api.get('/auth/me');
      set({ user, isAuthenticated: true, isLoading: false });
    } catch {
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },

  clearError: () => set({ error: null }),
}));
