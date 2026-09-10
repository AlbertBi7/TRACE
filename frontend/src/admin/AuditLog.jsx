/**
 * TRACE — Admin: Audit Log
 * Paginated, filterable audit log table for system-wide event tracking.
 */

import { useState, useEffect } from 'react';
import api from '../lib/api';
import { ScrollText, ChevronLeft, ChevronRight, Filter } from 'lucide-react';

export default function AuditLog() {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState('');

  useEffect(() => { fetchLogs(); }, [page, actionFilter]);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const params = { page, page_size: 25 };
      if (actionFilter) params.action = actionFilter;
      const { data } = await api.get('/api/audit', { params });
      setLogs(data.data);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  };

  const actionColor = (action) => {
    if (action.includes('LOGIN_SUCCESS')) return 'text-emerald-400';
    if (action.includes('LOGIN_FAILED')) return 'text-red-400';
    if (action.includes('CREATED')) return 'text-blue-400';
    if (action.includes('DEACTIVATED') || action.includes('DELETED')) return 'text-red-400';
    if (action.includes('UPDATED') || action.includes('RESET')) return 'text-amber-400';
    return 'text-trace-text-muted';
  };

  return (
    <div className="p-6 max-w-6xl mx-auto animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-trace-text flex items-center gap-2">
            <ScrollText className="w-6 h-6 text-trace-primary" /> Audit Log
          </h1>
          <p className="text-trace-text-muted text-sm mt-1">{total} total events</p>
        </div>

        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-trace-text-dim" />
          <select
            value={actionFilter}
            onChange={(e) => { setActionFilter(e.target.value); setPage(1); }}
            className="input-field w-48 text-sm py-1.5"
          >
            <option value="">All Actions</option>
            <option value="LOGIN_SUCCESS">Login Success</option>
            <option value="LOGIN_FAILED">Login Failed</option>
            <option value="LOGOUT">Logout</option>
            <option value="USER_CREATED">User Created</option>
            <option value="USER_UPDATED">User Updated</option>
            <option value="USER_DEACTIVATED">User Deactivated</option>
            <option value="PASSWORD_RESET">Password Reset</option>
            <option value="CASE_CREATED">Case Created</option>
            <option value="CASE_UPDATED">Case Updated</option>
            <option value="CASE_ASSIGNMENT">Case Assignment</option>
          </select>
        </div>
      </div>

      <div className="card overflow-hidden p-0">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="w-8 h-8 border-2 border-trace-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-trace-border">
                <th className="text-left text-xs font-medium text-trace-text-muted uppercase tracking-wider px-5 py-3">Timestamp</th>
                <th className="text-left text-xs font-medium text-trace-text-muted uppercase tracking-wider px-5 py-3">User</th>
                <th className="text-left text-xs font-medium text-trace-text-muted uppercase tracking-wider px-5 py-3">Action</th>
                <th className="text-left text-xs font-medium text-trace-text-muted uppercase tracking-wider px-5 py-3">Target</th>
                <th className="text-left text-xs font-medium text-trace-text-muted uppercase tracking-wider px-5 py-3">IP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-trace-border">
              {logs.map((log) => (
                <tr key={log.id} className="hover:bg-trace-surface-2 transition-colors">
                  <td className="px-5 py-3 text-xs text-trace-text-dim font-mono">
                    {new Date(log.timestamp).toLocaleString()}
                  </td>
                  <td className="px-5 py-3">
                    <p className="text-sm text-trace-text">{log.user_name || '—'}</p>
                    <p className="text-xs text-trace-text-dim">{log.user_email || 'system'}</p>
                  </td>
                  <td className="px-5 py-3">
                    <span className={`text-sm font-mono font-medium ${actionColor(log.action)}`}>{log.action}</span>
                  </td>
                  <td className="px-5 py-3 text-sm text-trace-text-muted">
                    {log.target_type && `${log.target_type}:${log.target_id?.substring(0, 8) || ''}`}
                  </td>
                  <td className="px-5 py-3 text-xs text-trace-text-dim font-mono">{log.ip_address || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <span className="text-sm text-trace-text-dim">
            Page {page} of {totalPages}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page === 1}
              className="btn-secondary py-1.5 px-3 flex items-center gap-1 text-sm disabled:opacity-30"
            >
              <ChevronLeft className="w-4 h-4" /> Prev
            </button>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page === totalPages}
              className="btn-secondary py-1.5 px-3 flex items-center gap-1 text-sm disabled:opacity-30"
            >
              Next <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
