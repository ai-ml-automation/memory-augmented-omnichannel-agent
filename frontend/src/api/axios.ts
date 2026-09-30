import axios from 'axios';
import toast from 'react-hot-toast';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor for error handling (Phase G.2)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Skip toast for cancelled requests
    if (axios.isCancel(error)) {
      return Promise.reject(error);
    }

    const status = error.response?.status;
    const message = error.response?.data?.detail || error.message;

    if (status === 401) {
      // Redirect to login on 401 (skip if already on login page)
      if (!window.location.pathname.includes('/login')) {
        toast.error('Сессия истекла. Войдите заново.');
        setTimeout(() => {
          window.location.href = '/login';
        }, 1000);
      }
    } else if (status === 403) {
      toast.error('Недостаточно прав для выполнения операции.');
    } else if (status === 404) {
      toast.error('Ресурс не найден.');
    } else if (status && status >= 500) {
      toast.error(`Ошибка сервера: ${message}`);
    } else if (!error.response) {
      toast.error('Нет соединения с сервером.');
    } else {
      // Other client errors
      toast.error(message || 'Произошла ошибка');
    }

    return Promise.reject(error);
  }
);

/**
 * Create an AbortController for request cancellation.
 * Usage: const { signal, cancel } = createAbortController();
 *        api.get('/endpoint', { signal });
 *        cancel(); // on unmount
 */
export function createAbortController() {
  const controller = new AbortController();
  return {
    signal: controller.signal,
    cancel: () => controller.abort(),
  };
}
