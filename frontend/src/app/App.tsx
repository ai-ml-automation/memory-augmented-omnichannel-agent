import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { useAuthStore } from '../store/auth.store';
import Layout from '../components/Layout';

// Existing pages
import { LoginPage } from '../pages/login';
import { RegisterPage } from '../pages/register';
import { DashboardPage } from '../pages/dashboard';
import OperatorDashboard from '../pages/operator';
import UsersPage from '../pages/operator/users';
import ChannelsPage from '../pages/operator/channels';
import AnalyticsDashboard from '../pages/operator/analytics';

// F.1 — Profile
import { ProfilePage } from '../pages/profile';
// F.2 — Session Detail
import SessionDetailPage from '../pages/operator/sessions/SessionDetail';
// F.3 — Sessions List
import { SessionsListPage } from '../pages/sessions';
// F.4 — Audit Log
import { AuditLogPage } from '../pages/audit';
// F.5 — Memory View
import { MemoryViewPage } from '../pages/memory';
// F.6 — Right to be Forgotten
import { ForgetPage } from '../pages/forget';
// F.7 — Admin Settings
import { AdminSettingsPage } from '../pages/admin/settings';
// F.8 — Voice Test
import { VoiceTestPage } from '../pages/voice-test';

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  return isAuthenticated ? (
    <Layout>{children}</Layout>
  ) : (
    <Navigate to="/login" />
  );
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  return isAuthenticated ? <Navigate to="/dashboard" /> : <>{children}</>;
}

const pageTransition = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.2, ease: 'easeInOut' as const },
};

function AnimatedRoutes() {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        initial={pageTransition.initial}
        animate={pageTransition.animate}
        exit={pageTransition.exit}
        transition={pageTransition.transition}
        className="h-full"
      >
        <Routes location={location}>
          {/* Public routes */}
          <Route
            path="/login"
            element={
              <PublicRoute>
                <LoginPage />
              </PublicRoute>
            }
          />
          <Route
            path="/register"
            element={
              <PublicRoute>
                <RegisterPage />
              </PublicRoute>
            }
          />

          {/* Protected routes — wrapped in Layout */}
          <Route
            path="/dashboard"
            element={
              <PrivateRoute>
                <DashboardPage />
              </PrivateRoute>
            }
          />

          <Route
            path="/profile"
            element={
              <PrivateRoute>
                <ProfilePage />
              </PrivateRoute>
            }
          />

          <Route
            path="/operator"
            element={
              <PrivateRoute>
                <OperatorDashboard />
              </PrivateRoute>
            }
          />
          <Route
            path="/operator/users"
            element={
              <PrivateRoute>
                <UsersPage />
              </PrivateRoute>
            }
          />
          <Route
            path="/operator/channels"
            element={
              <PrivateRoute>
                <ChannelsPage />
              </PrivateRoute>
            }
          />
          <Route
            path="/operator/analytics"
            element={
              <PrivateRoute>
                <AnalyticsDashboard />
              </PrivateRoute>
            }
          />

          <Route
            path="/sessions"
            element={
              <PrivateRoute>
                <SessionsListPage />
              </PrivateRoute>
            }
          />
          <Route
            path="/sessions/:id"
            element={
              <PrivateRoute>
                <SessionDetailPage />
              </PrivateRoute>
            }
          />

          <Route
            path="/audit"
            element={
              <PrivateRoute>
                <AuditLogPage />
              </PrivateRoute>
            }
          />

          <Route
            path="/memory/:userId"
            element={
              <PrivateRoute>
                <MemoryViewPage />
              </PrivateRoute>
            }
          />

          <Route
            path="/forget"
            element={
              <PrivateRoute>
                <ForgetPage />
              </PrivateRoute>
            }
          />

          <Route
            path="/admin/settings"
            element={
              <PrivateRoute>
                <AdminSettingsPage />
              </PrivateRoute>
            }
          />

          <Route
            path="/voice-test"
            element={
              <PrivateRoute>
                <VoiceTestPage />
              </PrivateRoute>
            }
          />

          {/* Default redirect */}
          <Route path="/" element={<Navigate to="/login" />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
}

function App() {
  return (
    <Router>
      <AnimatedRoutes />
    </Router>
  );
}

export default App;
