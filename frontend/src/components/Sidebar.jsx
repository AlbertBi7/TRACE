/**
 * TRACE — Sidebar Navigation
 * Collapsible sidebar with role-aware links, user info, and logout.
 */

import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  Shield,
  LayoutDashboard,
  FolderOpen,
  Network,
  Users,
  ScrollText,
  ChevronLeft,
  ChevronRight,
  LogOut,
  Settings,
  Zap,
} from 'lucide-react';

const investigatorLinks = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/dashboard/cases', icon: FolderOpen, label: 'Cases' },
];

const adminLinks = [
  { to: '/admin', icon: LayoutDashboard, label: 'Overview' },
  { to: '/admin/users', icon: Users, label: 'User Management' },
  { to: '/admin/cases', icon: FolderOpen, label: 'All Cases' },
  { to: '/admin/audit', icon: ScrollText, label: 'Audit Log' },
];

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();

  const links = isAdmin ? adminLinks : investigatorLinks;

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <aside
      className={`h-screen bg-trace-surface border-r border-trace-border flex flex-col transition-all duration-300 ${
        collapsed ? 'w-16' : 'w-60'
      }`}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 h-16 border-b border-trace-border flex-shrink-0">
        <div className="w-8 h-8 rounded-lg bg-trace-primary/10 border border-trace-primary/20 flex items-center justify-center flex-shrink-0">
          <Shield className="w-4 h-4 text-trace-primary" />
        </div>
        {!collapsed && (
          <div className="animate-fade-in">
            <h1 className="text-sm font-bold text-trace-text tracking-wide">TRACE</h1>
            <p className="text-[10px] text-trace-text-dim leading-none">Network Analysis</p>
          </div>
        )}
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/dashboard' || to === '/admin'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 group ${
                isActive
                  ? 'bg-trace-primary/10 text-trace-primary border border-trace-primary/20'
                  : 'text-trace-text-muted hover:text-trace-text hover:bg-trace-surface-2'
              }`
            }
          >
            <Icon className="w-4 h-4 flex-shrink-0" />
            {!collapsed && <span className="animate-fade-in">{label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* User Info & Actions */}
      <div className="border-t border-trace-border p-3 space-y-2">
        {/* Collapse toggle */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="w-full flex items-center justify-center p-2 rounded-lg text-trace-text-dim hover:text-trace-text hover:bg-trace-surface-2 transition-all"
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>

        {/* User card */}
        {!collapsed && user && (
          <div className="glass-light rounded-lg p-3 animate-fade-in">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-trace-primary/20 flex items-center justify-center text-xs font-bold text-trace-primary">
                {user.full_name?.charAt(0) || user.email.charAt(0).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-trace-text truncate">{user.full_name || user.email}</p>
                <p className={`text-[10px] ${isAdmin ? 'text-amber-400' : 'text-blue-400'}`}>
                  {user.role}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Logout */}
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-trace-text-muted hover:text-trace-danger hover:bg-trace-danger/5 transition-all"
        >
          <LogOut className="w-4 h-4 flex-shrink-0" />
          {!collapsed && <span>Sign Out</span>}
        </button>
      </div>
    </aside>
  );
}
