/**
 * TRACE — Dashboard Home / Case List Page
 * Shows assigned cases (investigators) or all cases (admins).
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api from '../lib/api';
import { FolderOpen, Plus, Search, Filter, Clock, ChevronRight } from 'lucide-react';

export default function CaseListPage() {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [newCase, setNewCase] = useState({ name: '', description: '' });
  const [creating, setCreating] = useState(false);
  const { user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    fetchCases();
  }, []);

  const fetchCases = async () => {
    try {
      const { data } = await api.get('/api/cases');
      setCases(data);
    } catch (err) {
      console.error('Failed to fetch cases:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setCreating(true);
    try {
      await api.post('/api/cases', newCase);
      setShowCreate(false);
      setNewCase({ name: '', description: '' });
      fetchCases();
    } catch (err) {
      console.error('Failed to create case:', err);
    } finally {
      setCreating(false);
    }
  };

  const filteredCases = cases.filter(
    (c) =>
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.description.toLowerCase().includes(search.toLowerCase())
  );

  const statusBadge = (status) => {
    const cls = { open: 'badge-open', closed: 'badge-closed', archived: 'badge-archived' };
    return <span className={cls[status] || 'badge'}>{status}</span>;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-trace-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-trace-text">Cases</h1>
          <p className="text-trace-text-muted text-sm mt-1">
            {user?.role === 'admin' ? 'All system cases' : 'Your assigned investigations'}
          </p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" />
          New Case
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-trace-text-dim" />
        <input
          type="text"
          placeholder="Search cases..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="input-field pl-10"
        />
      </div>

      {/* Create Case Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="glass rounded-2xl p-6 w-full max-w-md animate-slide-in-up">
            <h2 className="text-lg font-semibold text-trace-text mb-4">Create New Case</h2>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm text-trace-text-muted mb-1">Case Name</label>
                <input
                  type="text"
                  value={newCase.name}
                  onChange={(e) => setNewCase({ ...newCase, name: e.target.value })}
                  required
                  className="input-field"
                  placeholder="e.g., Operation Nexus"
                />
              </div>
              <div>
                <label className="block text-sm text-trace-text-muted mb-1">Description</label>
                <textarea
                  value={newCase.description}
                  onChange={(e) => setNewCase({ ...newCase, description: e.target.value })}
                  className="input-field h-24 resize-none"
                  placeholder="Brief description of the investigation..."
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowCreate(false)} className="btn-secondary flex-1">
                  Cancel
                </button>
                <button type="submit" disabled={creating} className="btn-primary flex-1">
                  {creating ? 'Creating...' : 'Create Case'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Case Grid */}
      {filteredCases.length === 0 ? (
        <div className="text-center py-16">
          <FolderOpen className="w-12 h-12 text-trace-text-dim mx-auto mb-3" />
          <p className="text-trace-text-muted">No cases found</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredCases.map((c) => (
            <button
              key={c.id}
              onClick={() => navigate(`/dashboard/cases/${c.id}`)}
              className="card text-left group hover:border-trace-primary/30 hover:shadow-lg hover:shadow-trace-primary/5"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="w-10 h-10 rounded-lg bg-trace-primary/10 flex items-center justify-center">
                  <FolderOpen className="w-5 h-5 text-trace-primary" />
                </div>
                {statusBadge(c.status)}
              </div>
              <h3 className="font-semibold text-trace-text mb-1 group-hover:text-trace-primary transition-colors">
                {c.name}
              </h3>
              <p className="text-sm text-trace-text-muted line-clamp-2 mb-3">
                {c.description || 'No description'}
              </p>
              <div className="flex items-center justify-between text-xs text-trace-text-dim">
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {new Date(c.created_at).toLocaleDateString()}
                </span>
                <ChevronRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity text-trace-primary" />
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
