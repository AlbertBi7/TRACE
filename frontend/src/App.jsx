/**
 * TRACE — Main Application
 * Root component with React Router, AuthContext, role-guarded routes.
 */

import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Sidebar from './components/Sidebar';
import LoginPage from './auth/LoginPage';
import CaseListPage from './dashboard/CaseListPage';
import CaseDetailPage from './dashboard/CaseDetailPage';
import GraphExplorer from './dashboard/GraphExplorer';
import UserManagement from './admin/UserManagement';
import AuditLog from './admin/AuditLog';
import CaseOverview from './admin/CaseOverview';

function AppLayout() {
  return (
    <div className="flex h-screen bg-trace-bg overflow-hidden">
      <Sidebar />
      <main className="min-h-0 flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}

function AdminDashboard() {
  return (
    <div className="p-6 max-w-6xl mx-auto animate-fade-in">
      <h1 className="text-2xl font-bold text-trace-text mb-2">Admin Dashboard</h1>
      <p className="text-trace-text-muted text-sm mb-8">System overview and management</p>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="card">
          <p className="text-trace-text-muted text-sm mb-1">Navigation</p>
          <p className="text-trace-text text-sm">Use the sidebar to manage users, cases, and view audit logs.</p>
        </div>
      </div>
    </div>
  );
}

function InvestigatorDashboard() {
  return <CaseListPage />;
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<LoginPage />} />

          {/* Investigator Routes */}
          <Route
            element={
              <ProtectedRoute allowedRoles={['investigator', 'admin']}>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route path="/dashboard" element={<InvestigatorDashboard />} />
            <Route path="/dashboard/cases" element={<CaseListPage />} />
            <Route path="/dashboard/cases/:caseId" element={<CaseDetailPage />} />
            <Route path="/dashboard/cases/:caseId/graph" element={<GraphExplorer />} />
          </Route>

          {/* Admin Routes */}
          <Route
            element={
              <ProtectedRoute allowedRoles={['admin']}>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route path="/admin" element={<AdminDashboard />} />
            <Route path="/admin/users" element={<UserManagement />} />
            <Route path="/admin/cases" element={<CaseOverview />} />
            <Route path="/admin/audit" element={<AuditLog />} />
          </Route>

          {/* Default redirect */}
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
