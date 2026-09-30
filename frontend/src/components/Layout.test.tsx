import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Layout from '../components/Layout';

// Mock the auth store
vi.mock('../store/auth.store', () => ({
  useAuthStore: () => ({
    user: { id: 'user-1', phone_hash: 'hashed-phone', role: 'operator' },
    isAuthenticated: true,
    logout: vi.fn(),
  }),
}));

function renderWithRouter(ui: React.ReactElement, { route = '/' } = {}) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      {ui}
    </MemoryRouter>
  );
}

describe('Layout', () => {
  it('renders navigation links', () => {
    renderWithRouter(<Layout>Content</Layout>, { route: '/dashboard' });
    expect(screen.getByText('Главная')).toBeInTheDocument();
    expect(screen.getByText('Сессии')).toBeInTheDocument();
    expect(screen.getByText('Аудит')).toBeInTheDocument();
    expect(screen.getByText('Настройки')).toBeInTheDocument();
    expect(screen.getByText('Тест голоса')).toBeInTheDocument();
  });

  it('renders children', () => {
    renderWithRouter(<Layout>Test Content</Layout>, { route: '/dashboard' });
    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });

  it('renders logo text', () => {
    renderWithRouter(<Layout>Content</Layout>, { route: '/dashboard' });
    expect(screen.getAllByText('Мой Агент').length).toBeGreaterThan(0);
  });

  it('shows user phone hash', () => {
    renderWithRouter(<Layout>Content</Layout>, { route: '/dashboard' });
    expect(screen.getByText('hashed-phone')).toBeInTheDocument();
  });

  it('highlights active route', () => {
    renderWithRouter(<Layout>Content</Layout>, { route: '/sessions' });
    const sessionsLink = screen.getByText('Сессии');
    expect(sessionsLink.closest('a')).toHaveClass('bg-primary/10');
  });

  it('renders logout button', () => {
    renderWithRouter(<Layout>Content</Layout>, { route: '/dashboard' });
    expect(screen.getByText('Выйти')).toBeInTheDocument();
  });
});
