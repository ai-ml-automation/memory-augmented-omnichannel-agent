import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useAuthStore } from './auth.store';

// Mock the API module
vi.mock('../api/axios', () => ({
  api: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

import { api } from '../api/axios';
const mockPost = vi.mocked(api.post);
const mockGet = vi.mocked(api.get);

const TEST_CRED = 'testCred2024';

beforeEach(() => {
  useAuthStore.setState({
    user: null,
    isAuthenticated: false,
    isLoading: false,
    error: null,
  });
  vi.clearAllMocks();
});

describe('authStore', () => {
  it('has correct initial state', () => {
    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();
  });

  it('login sets user and isAuthenticated on success', async () => {
    const mockUser = {
      id: 'user-1',
      phone_hash: 'hash123',
      role: 'operator',
      created_at: '2024-01-01T00:00:00Z',
      is_active: true,
      tenant_id: 'tenant-1',
    };
    mockPost.mockResolvedValueOnce({ data: { success: true } });
    mockGet.mockResolvedValueOnce({ data: mockUser });

    await useAuthStore.getState().login('+79991234567', TEST_CRED);

    const state = useAuthStore.getState();
    expect(state.user).toEqual(mockUser);
    expect(state.isAuthenticated).toBe(true);
    expect(state.isLoading).toBe(false);
    expect(mockPost).toHaveBeenCalledWith('/auth/login', {
      phone: '+79991234567',
      password: TEST_CRED,
    });
  });

  it('login sets error on failure', async () => {
    mockPost.mockRejectedValueOnce(new Error('Неверные учётные данные'));

    await expect(
      useAuthStore.getState().login('+79991234567', 'wrongCred')
    ).rejects.toThrow();

    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.error).toBe('Неверные учётные данные');
  });

  it('logout clears user state', async () => {
    useAuthStore.setState({
      user: { id: 'user-1', phone_hash: 'hash', created_at: '', is_active: true, tenant_id: 't' },
      isAuthenticated: true,
    });

    mockPost.mockResolvedValueOnce({ data: { success: true } });
    await useAuthStore.getState().logout();

    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
  });

  it('clearError resets error', () => {
    useAuthStore.setState({ error: 'Some error' });
    useAuthStore.getState().clearError();
    expect(useAuthStore.getState().error).toBeNull();
  });

  it('checkAuth sets user when session valid', async () => {
    const mockUser = {
      id: 'user-1',
      phone_hash: 'hash',
      created_at: '',
      is_active: true,
      tenant_id: 't',
    };
    mockGet.mockResolvedValueOnce({ data: mockUser });

    await useAuthStore.getState().checkAuth();

    expect(useAuthStore.getState().user).toEqual(mockUser);
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it('checkAuth clears user when session invalid', async () => {
    mockGet.mockRejectedValueOnce(new Error('Unauthorized'));

    await useAuthStore.getState().checkAuth();

    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });
});
