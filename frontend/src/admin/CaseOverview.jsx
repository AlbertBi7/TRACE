/**
 * TRACE — Admin: Case Overview
 * View all cases system-wide and manage assignments.
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../lib/api';
import { FolderOpen, Clock, Users, Plus, X } from 'lucide-react';

export default function CaseOverview() {
  const [cases, setCases] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [assignModal, setAssignModal] = useState(null); // case_id or null
  const [selectedUser, setSelectedUser] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([
      api.get('/api/cases').then(r => setCases(r.data)),
      api.get('/api/users').then(r => setUsers(r.data)),
    ]).finally(() => setLoading(false));
  }, []);

  const handleAssign = async () => {
    if (!selectedUser) return;
    try {
      await api.post(`/api/cases/${assignModal}/assign`, { user_id: selectedUser });
      setAssignModal(null);
      setSelectedUser('');
      // Refresh
      const { data } = await api.get('/api/cases');
      setCases(data);
    } catch (err) { alert(err.response?.data?.detail || 'Failed to assign'); }
  };

  const statusBadge = (status) => {
    const cls = { open: 'badge-open', closed: 'badge-closed', archived: 'badge-archived' };
    return <span className={cls[status] || 'badge'}>{status}</span>;
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-2 border-trace-primary border-t-transparent rounded-full animate-spin" />
    </div>;
  }

  return (
    <div className="p-6 max-w-6xl mx-auto animate-fade-in">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-trace-text flex items-center gap-2">
          <FolderOpen className="w-6 h-6 text-trace-primary" /> All Cases
        </h1>
        <p className="text-trace-text-muted text-sm mt-1">{cases.length} cases in the system</p>
      </div>

      {/* Assign Modal */}
      {assignModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="glass rounded-2xl p-6 w-full max-w-sm animate-slide-in-up">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-trace-text">Assign Investigator</h2>
              <button onClick={() => setAssignModal(null)} className="text-trace-text-dim hover:text-trace-text"><X className="w-5 h-5" /></button>
            </div>
            <select value={selectedUser} onChange={(e) => setSelectedUser(e.target.value)} className="input-field mb-4">
              <option value="">Select user...</option>
              {users.filter(u => u.is_active && u.role === 'investigator').map(u => (
                <option key={u.id} value={u.id}>{u.full_name} ({u.role})</option>
              ))}
            </select>
            <div className="flex gap-3">
              <button onClick={() => setAssignModal(null)} className="btn-secondary flex-1">Cancel</button>
              <button onClick={handleAssign} disabled={!selectedUser} className="btn-primary flex-1">Assign</button>
            </div>
          </div>
        </div>
      )}

      {/* Cases Table */}
      <div className="card overflow-hidden p-0">
        <table className="w-full">
          <thead>
            <tr className="border-b border-trace-border">
              <th className="text-left text-xs font-medium text-trace-text-muted uppercase tracking-wider px-5 py-3">Case</th>
              <th className="text-left text-xs font-medium text-trace-text-muted uppercase tracking-wider px-5 py-3">Status</th>
              <th className="text-left text-xs font-medium text-trace-text-muted uppercase tracking-wider px-5 py-3">Created</th>
              <th className="text-right text-xs font-medium text-trace-text-muted uppercase tracking-wider px-5 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-trace-border">
            {cases.map((c) => (
              <tr key={c.id} className="hover:bg-trace-surface-2 transition-colors">
                <td className="px-5 py-3">
                  <p className="text-sm font-medium text-trace-text">{c.name}</p>
                  <p className="text-xs text-trace-text-dim truncate max-w-xs">{c.description || 'No description'}</p>
                </td>
                <td className="px-5 py-3">{statusBadge(c.status)}</td>
                <td className="px-5 py-3 text-sm text-trace-text-dim">
                  <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {new Date(c.created_at).toLocaleDateString()}</span>
                </td>
                <td className="px-5 py-3 text-right">
                  <button onClick={() => setAssignModal(c.id)} className="btn-secondary py-1 px-3 text-xs flex items-center gap-1 ml-auto">
                    <Users className="w-3 h-3" /> Assign
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
