/**
 * TRACE — Admin: User Management
 * Create, list, deactivate, and reset passwords for user accounts.
 */

import { useState, useEffect } from 'react';
import api from '../lib/api';
import { Users, Plus, Shield, UserCheck, UserX, Key, X } from 'lucide-react';

export default function UserManagement() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newUser, setNewUser] = useState({ email: '', password: '', full_name: '', role: 'investigator' });
  const [creating, setCreating] = useState(false);
  const [resetTarget, setResetTarget] = useState(null);
  const [newPassword, setNewPassword] = useState('');

  useEffect(() => { fetchUsers(); }, []);

  const fetchUsers = async () => {
    try {
      const { data } = await api.get('/api/users');
      setUsers(data);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setCreating(true);
    try {
      await api.post('/api/users', newUser);
      setShowCreate(false);
      setNewUser({ email: '', password: '', full_name: '', role: 'investigator' });
      fetchUsers();
    } catch (err) { alert(err.response?.data?.detail || 'Failed to create user'); }
    finally { setCreating(false); }
  };

  const toggleActive = async (userId, isActive) => {
    try {
      if (isActive) {
        await api.delete(`/api/users/${userId}`);
      } else {
        await api.patch(`/api/users/${userId}`, { is_active: true });
      }
      fetchUsers();
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    try {
      await api.post(`/api/users/${resetTarget}/reset-password`, { new_password: newPassword });
      setResetTarget(null);
      setNewPassword('');
      alert('Password reset successfully');
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-2 border-trace-primary border-t-transparent rounded-full animate-spin" />
    </div>;
  }

  return (
    <div className="p-6 max-w-5xl mx-auto animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-trace-text flex items-center gap-2">
            <Users className="w-6 h-6 text-trace-primary" /> User Management
          </h1>
          <p className="text-trace-text-muted text-sm mt-1">{users.length} registered users</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" /> Add User
        </button>
      </div>

      {/* Create User Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="glass rounded-2xl p-6 w-full max-w-md animate-slide-in-up">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-trace-text">Create User</h2>
              <button onClick={() => setShowCreate(false)} className="text-trace-text-dim hover:text-trace-text"><X className="w-5 h-5" /></button>
            </div>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm text-trace-text-muted mb-1">Full Name</label>
                <input type="text" value={newUser.full_name} onChange={(e) => setNewUser({ ...newUser, full_name: e.target.value })} required className="input-field" />
              </div>
              <div>
                <label className="block text-sm text-trace-text-muted mb-1">Email</label>
                <input type="email" value={newUser.email} onChange={(e) => setNewUser({ ...newUser, email: e.target.value })} required className="input-field" />
              </div>
              <div>
                <label className="block text-sm text-trace-text-muted mb-1">Password</label>
                <input type="password" value={newUser.password} onChange={(e) => setNewUser({ ...newUser, password: e.target.value })} required minLength={8} className="input-field" />
              </div>
              <div>
                <label className="block text-sm text-trace-text-muted mb-1">Role</label>
                <select value={newUser.role} onChange={(e) => setNewUser({ ...newUser, role: e.target.value })} className="input-field">
                  <option value="investigator">Investigator</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowCreate(false)} className="btn-secondary flex-1">Cancel</button>
                <button type="submit" disabled={creating} className="btn-primary flex-1">{creating ? 'Creating...' : 'Create'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Password Reset Modal */}
      {resetTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="glass rounded-2xl p-6 w-full max-w-sm animate-slide-in-up">
            <h2 className="text-lg font-semibold text-trace-text mb-4">Reset Password</h2>
            <form onSubmit={handleResetPassword} className="space-y-4">
              <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required minLength={8} placeholder="New password (min 8 chars)" className="input-field" />
              <div className="flex gap-3">
                <button type="button" onClick={() => { setResetTarget(null); setNewPassword(''); }} className="btn-secondary flex-1">Cancel</button>
                <button type="submit" className="btn-primary flex-1">Reset</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Users Table */}
      <div className="card overflow-hidden p-0">
        <table className="w-full">
          <thead>
            <tr className="border-b border-trace-border">
              <th className="text-left text-xs font-medium text-trace-text-muted uppercase tracking-wider px-5 py-3">User</th>
              <th className="text-left text-xs font-medium text-trace-text-muted uppercase tracking-wider px-5 py-3">Role</th>
              <th className="text-left text-xs font-medium text-trace-text-muted uppercase tracking-wider px-5 py-3">Status</th>
              <th className="text-left text-xs font-medium text-trace-text-muted uppercase tracking-wider px-5 py-3">Last Login</th>
              <th className="text-right text-xs font-medium text-trace-text-muted uppercase tracking-wider px-5 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-trace-border">
            {users.map((u) => (
              <tr key={u.id} className="hover:bg-trace-surface-2 transition-colors">
                <td className="px-5 py-3">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-trace-primary/20 flex items-center justify-center text-xs font-bold text-trace-primary">
                      {u.full_name?.charAt(0) || '?'}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-trace-text">{u.full_name}</p>
                      <p className="text-xs text-trace-text-dim">{u.email}</p>
                    </div>
                  </div>
                </td>
                <td className="px-5 py-3">
                  <span className={u.role === 'admin' ? 'badge-admin' : 'badge-investigator'}>{u.role}</span>
                </td>
                <td className="px-5 py-3">
                  <span className={u.is_active ? 'badge-open' : 'badge-closed'}>{u.is_active ? 'Active' : 'Inactive'}</span>
                </td>
                <td className="px-5 py-3 text-sm text-trace-text-dim">
                  {u.last_login ? new Date(u.last_login).toLocaleString() : 'Never'}
                </td>
                <td className="px-5 py-3 text-right">
                  <div className="flex items-center justify-end gap-1">
                    <button onClick={() => setResetTarget(u.id)} title="Reset password" className="p-2 rounded-lg hover:bg-trace-surface-3 text-trace-text-dim hover:text-trace-accent transition-colors">
                      <Key className="w-4 h-4" />
                    </button>
                    <button onClick={() => toggleActive(u.id, u.is_active)} title={u.is_active ? 'Deactivate' : 'Activate'} className="p-2 rounded-lg hover:bg-trace-surface-3 text-trace-text-dim hover:text-trace-danger transition-colors">
                      {u.is_active ? <UserX className="w-4 h-4" /> : <UserCheck className="w-4 h-4" />}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
