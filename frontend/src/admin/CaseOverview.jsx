/**
 * TRACE — Admin: Case Overview
 * View all cases system-wide, manage assignments, and monitor investigative pulse.
 * Now with live KPIs, status pulse, activity sparkline, and cross-case insights.
 */

import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../lib/api';
import {
  FolderOpen, Clock, Users, Plus, X, Activity, Shield, FileText, Network,
  TrendingUp, AlertTriangle, CheckCircle2, Archive, Zap, Eye, GitBranch, Layers, Trash2
} from 'lucide-react';

export default function CaseOverview() {
  const [cases, setCases] = useState([]);
  const [users, setUsers] = useState([]);
  const [audit, setAudit] = useState([]);
  const [caseNetwork, setCaseNetwork] = useState(null);
  const [loading, setLoading] = useState(true);
  const [assignModal, setAssignModal] = useState(null);
  const [selectedUser, setSelectedUser] = useState('');
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [health, setHealth] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([
      api.get('/api/cases').then(r => !cancelled && setCases(r.data)),
      api.get('/api/users').then(r => !cancelled && setUsers(r.data)),
      api.get('/api/audit', { params: { page: 1, page_size: 20 } }).then(r => !cancelled && setAudit(r.data?.data || [])),
      api.get('/api/analysis/case-network').then(r => !cancelled && setCaseNetwork(r.data)).catch(() => {}),
      api.get('/api/health').then(r => !cancelled && setHealth(r.data)).catch(() => {}),
    ]).finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, []);

  const handleAssign = async () => {
    if (!selectedUser) return;
    try {
      await api.post(`/api/cases/${assignModal}/assign`, { user_id: selectedUser });
      setAssignModal(null);
      setSelectedUser('');
      const { data } = await api.get('/api/cases');
      setCases(data);
    } catch (err) { alert(err.response?.data?.detail || 'Failed to assign'); }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api.delete(`/api/cases/${deleteTarget.id}`);
      setCases(prev => prev.filter(c => c.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (err) {
      alert(err.response?.data?.detail || 'Delete failed — admin only');
    } finally {
      setDeleting(false);
    }
  };

  const stats = useMemo(() => {
    const total = cases.length;
    const open = cases.filter(c => c.status === 'open').length;
    const closed = cases.filter(c => c.status === 'closed').length;
    const archived = cases.filter(c => c.status === 'archived').length;
    const investigators = users.filter(u => u.role === 'investigator' && u.is_active).length;
    const admins = users.filter(u => u.role === 'admin' && u.is_active).length;
    const recent = [...cases].sort((a,b)=> new Date(b.created_at)-new Date(a.created_at)).slice(0,4);
    // Cases per month for sparkline (last 6 months)
    const buckets = Array.from({length:6}, (_,i)=>{
      const d = new Date(); d.setMonth(d.getMonth()-(5-i));
      const key = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;
      const label = d.toLocaleString('default',{month:'short'});
      return { key, label, count:0 };
    });
    const map = Object.fromEntries(buckets.map(b=>[b.key,b]));
    cases.forEach(c=>{
      const d=new Date(c.created_at); const k=`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;
      if(map[k]) map[k].count++;
    });
    const max = Math.max(1, ...buckets.map(b=>b.count));
    const assignmentsPending = cases.length ? Math.round((closed/total||0)*100) : 0;
    return { total, open, closed, archived, investigators, admins, recent, buckets, max, assignmentsPending };
  }, [cases, users]);

  const crossCaseInsights = useMemo(()=>{
    if(!caseNetwork) return null;
    const nodes = caseNetwork.nodes||[];
    const edges = caseNetwork.edges||[];
    const dense = [...edges].sort((a,b)=>b.shared_count-a.shared_count).slice(0,3);
    return { nodeCount:nodes.length, edgeCount:edges.length, dense };
  }, [caseNetwork]);

  const statusBadge = (status) => {
    const cls = { open: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30', closed: 'bg-amber-500/15 text-amber-400 border-amber-500/30', archived: 'bg-slate-500/15 text-slate-400 border-slate-500/30' };
    return <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-medium border ${cls[status] || 'bg-slate-500/10 text-slate-400 border-slate-500/20'}`}>{status}</span>;
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64"><div className="w-8 h-8 border-2 border-trace-primary border-t-transparent rounded-full animate-spin" /></div>;
  }

  return (
    <div className="p-6 max-w-7xl mx-auto animate-fade-in space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-trace-text flex items-center gap-2">
            <span className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-600/20"><Shield className="w-5 h-5 text-white" /></span>
            Command Center
          </h1>
          <p className="text-trace-text-muted text-sm mt-1">Live pulse of investigative operations — {stats.total} cases · {users.length} users · <span className={`inline-flex items-center gap-1 ${health?.status==='healthy'?'text-emerald-400':'text-amber-400'}`}><span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse"/>{health?.status || 'checking'}</span></p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={()=>navigate('/admin/audit')} className="btn-secondary py-2 px-3 text-xs flex items-center gap-1.5"><Activity className="w-3.5 h-3.5"/> Audit trail</button>
          <button onClick={()=>navigate('/admin/users')} className="btn-secondary py-2 px-3 text-xs flex items-center gap-1.5"><Users className="w-3.5 h-3.5"/> Manage users</button>
        </div>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card p-4 relative overflow-hidden group hover:border-violet-500/30 transition-colors">
          <div className="absolute -right-6 -top-6 w-20 h-20 rounded-full bg-gradient-to-br from-violet-600/20 to-indigo-600/20 blur-2xl group-hover:from-violet-600/30 transition-all"/>
          <div className="flex items-center justify-between">
            <span className="w-8 h-8 rounded-lg bg-violet-500/15 flex items-center justify-center"><FolderOpen className="w-4 h-4 text-violet-400"/></span>
            <span className="text-[11px] px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-300 border border-violet-500/20 flex items-center gap-1"><TrendingUp className="w-3 h-3"/>{stats.open} open</span>
          </div>
          <p className="text-2xl font-bold text-trace-text mt-3">{stats.total}</p>
          <p className="text-xs text-trace-text-dim">Total cases</p>
          <div className="mt-3 flex gap-1 h-1.5">
            {['open','closed','archived'].map(k=>{
              const v = stats[k]; const pct = stats.total? (v/stats.total)*100 : 0;
              const col = k==='open'?'bg-emerald-500':k==='closed'?'bg-amber-500':'bg-slate-500';
              return <div key={k} className={`${col} rounded-full transition-all`} style={{width:`${pct}%`}} title={`${k}: ${v}`}/>;
            })}
          </div>
        </div>

        <div className="card p-4 relative overflow-hidden group hover:border-emerald-500/30 transition-colors">
          <div className="absolute -right-6 -top-6 w-20 h-20 rounded-full bg-emerald-500/10 blur-2xl"/>
          <div className="flex items-center justify-between">
            <span className="w-8 h-8 rounded-lg bg-emerald-500/15 flex items-center justify-center"><Users className="w-4 h-4 text-emerald-400"/></span>
            <span className="text-[11px] text-trace-text-dim">{stats.admins} admins</span>
          </div>
          <p className="text-2xl font-bold text-trace-text mt-3">{stats.investigators}</p>
          <p className="text-xs text-trace-text-dim">Active investigators</p>
          <div className="mt-2 text-[11px] text-trace-text-muted flex items-center gap-1"><CheckCircle2 className="w-3 h-3 text-emerald-400"/> {users.filter(u=>u.is_active).length} active / {users.length} total</div>
        </div>

        <div className="card p-4 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="w-8 h-8 rounded-lg bg-sky-500/15 flex items-center justify-center"><Network className="w-4 h-4 text-sky-400"/></span>
            <span className="text-[11px] px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-300 border border-sky-500/20">{crossCaseInsights?.edgeCount ?? 0} links</span>
          </div>
          <p className="text-2xl font-bold text-trace-text mt-3">{crossCaseInsights?.nodeCount ?? stats.total}</p>
          <p className="text-xs text-trace-text-dim">Cases in cross-case graph</p>
          <div className="mt-2 flex items-center gap-1 text-[11px] text-trace-text-muted"><GitBranch className="w-3 h-3"/> {crossCaseInsights?.dense?.length ? `${crossCaseInsights.dense[0].shared_count} shared entities (top)` : 'No recurring entities yet'}</div>
        </div>

        <div className="card p-4 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="w-8 h-8 rounded-lg bg-amber-500/15 flex items-center justify-center"><Zap className="w-4 h-4 text-amber-400"/></span>
            <span className={`text-[11px] px-2 py-0.5 rounded-full border ${stats.closed ? 'bg-amber-500/10 text-amber-300 border-amber-500/20' : 'bg-slate-500/10 text-slate-400 border-slate-500/20'}`}>{stats.assignmentsPending}% closed</span>
          </div>
          <p className="text-2xl font-bold text-trace-text mt-3">{audit.length}</p>
          <p className="text-xs text-trace-text-dim">Recent audit events</p>
          <div className="mt-2 text-[11px] text-trace-text-muted truncate">{audit[0]?.action || 'No recent activity'} · {audit[0] ? new Date(audit[0].timestamp).toLocaleDateString() : '—'}</div>
        </div>
      </div>

      {/* Sparkline + Status Pulse */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="card p-4 lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-trace-text flex items-center gap-2"><Activity className="w-4 h-4 text-violet-400"/> Case creation — last 6 months</h3>
            <span className="text-xs text-trace-text-dim">{stats.total} total</span>
          </div>
          <div className="flex items-end gap-2 h-20 px-2">
            {stats.buckets.map(b=>{
              const h = (b.count / stats.max) * 64 + 6;
              return (
                <div key={b.key} className="flex-1 flex flex-col items-center gap-1">
                  <span className="text-[10px] text-trace-text-dim font-mono">{b.count}</span>
                  <div className="w-full rounded-t-md bg-gradient-to-t from-violet-600/40 to-indigo-500/60 border border-violet-500/20 hover:from-violet-500/60 hover:to-indigo-400/70 transition-all" style={{height:h}} title={`${b.label}: ${b.count}`}/>
                  <span className="text-[10px] text-trace-text-muted">{b.label}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="card p-4">
          <h3 className="text-sm font-semibold text-trace-text flex items-center gap-2 mb-3"><Layers className="w-4 h-4 text-emerald-400"/> Status pulse</h3>
          <div className="space-y-3">
            {[
              {k:'open', label:'Open', icon:AlertTriangle, color:'emerald', count:stats.open},
              {k:'closed', label:'Closed', icon:CheckCircle2, color:'amber', count:stats.closed},
              {k:'archived', label:'Archived', icon:Archive, color:'slate', count:stats.archived},
            ].map(row=>{
              const pct = stats.total ? Math.round(row.count/stats.total*100) : 0;
              const Icon = row.icon;
              return (
                <div key={row.k} className="flex items-center gap-3">
                  <span className={`w-7 h-7 rounded-lg flex items-center justify-center ${row.color==='emerald'?'bg-emerald-500/15 text-emerald-400':row.color==='amber'?'bg-amber-500/15 text-amber-400':'bg-slate-500/15 text-slate-400'}`}><Icon className="w-3.5 h-3.5"/></span>
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-trace-text">{row.label}</span>
                      <span className="text-xs font-mono text-trace-text-muted">{row.count} · {pct}%</span>
                    </div>
                    <div className="h-1.5 w-full bg-trace-surface-3 rounded-full mt-1 overflow-hidden">
                      <div className={`h-full rounded-full ${row.color==='emerald'?'bg-emerald-500':row.color==='amber'?'bg-amber-500':'bg-slate-500'}`} style={{width:`${pct}%`}}/>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          {crossCaseInsights?.dense?.length >0 && (
            <div className="mt-4 p-2.5 rounded-lg bg-sky-500/10 border border-sky-500/20">
              <p className="text-xs font-medium text-sky-300 flex items-center gap-1"><GitBranch className="w-3 h-3"/> Top cross-case link</p>
              <p className="text-xs text-trace-text-muted mt-1 truncate">{crossCaseInsights.dense[0].source.slice(0,8)} ↔ {crossCaseInsights.dense[0].target.slice(0,8)} · {crossCaseInsights.dense[0].shared_count} shared</p>
            </div>
          )}
        </div>
      </div>

      {/* Recent + Insights */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="card p-0 overflow-hidden lg:col-span-2">
          <div className="px-4 py-3 border-b border-trace-border flex items-center justify-between">
            <h3 className="text-sm font-semibold text-trace-text flex items-center gap-2"><Clock className="w-4 h-4 text-sky-400"/> Recent cases</h3>
            <span className="text-xs text-trace-text-dim">{stats.recent.length} shown</span>
          </div>
          <div className="divide-y divide-trace-border">
            {stats.recent.map(c=>(
              <div key={c.id} className="px-4 py-3 flex items-center justify-between hover:bg-trace-surface-2 transition-colors">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-trace-text truncate">{c.name}</p>
                  <p className="text-xs text-trace-text-dim truncate max-w-[32ch]">{c.description || 'No description'}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0 ml-3">
                  {statusBadge(c.status)}
                  <button onClick={()=>setAssignModal(c.id)} className="btn-secondary py-1 px-2 text-xs"><Users className="w-3 h-3"/></button>
                  <button onClick={()=>navigate(`/dashboard/cases/${c.id}`)} className="btn-ghost p-1.5"><Eye className="w-4 h-4 text-trace-text-dim"/></button>
                  <button onClick={()=>setDeleteTarget(c)} title="Delete case (admin)" className="p-1.5 rounded-lg hover:bg-red-500/10 text-trace-text-dim hover:text-red-400 transition-colors"><Trash2 className="w-3.5 h-3.5"/></button>
                </div>
              </div>
            ))}
            {!stats.recent.length && <p className="p-6 text-sm text-trace-text-dim text-center">No cases yet — create the first one to see pulse.</p>}
          </div>
        </div>

        <div className="space-y-4">
          <div className="card p-4 bg-gradient-to-br from-violet-600/10 via-indigo-600/10 to-sky-600/10 border-violet-500/20">
            <h3 className="text-sm font-semibold text-trace-text flex items-center gap-2"><FileText className="w-4 h-4 text-violet-400"/> Investigative tip</h3>
            <p className="text-xs text-trace-text-muted mt-2 leading-relaxed">Graph Sync is <span className="text-trace-text font-medium">idempotent</span> — re-run it after every merge. Provenance stays in <span className="text-trace-text">Postgres</span>, Neo4j is rebuildable.</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {['OCR preserves page/para','FHIR not needed','No guilt scores'].map(t=><span key={t} className="text-[10px] px-2 py-1 rounded-full bg-trace-surface-2 border border-trace-border text-trace-text-dim">{t}</span>)}
            </div>
          </div>

          <div className="card p-4">
            <h3 className="text-sm font-semibold text-trace-text mb-2">Quick actions</h3>
            <div className="grid grid-cols-2 gap-2">
              <button onClick={()=>navigate('/admin/users')} className="p-3 rounded-xl bg-trace-surface-2 hover:bg-trace-surface-3 border border-trace-border text-left transition-colors">
                <Users className="w-4 h-4 text-emerald-400"/><p className="text-xs font-medium text-trace-text mt-1">Manage team</p><p className="text-[11px] text-trace-text-dim">{stats.investigators} active</p>
              </button>
              <button onClick={()=>navigate('/dashboard/case-network')} className="p-3 rounded-xl bg-trace-surface-2 hover:bg-trace-surface-3 border border-trace-border text-left transition-colors">
                <Network className="w-4 h-4 text-sky-400"/><p className="text-xs font-medium text-trace-text mt-1">Case graph</p><p className="text-[11px] text-trace-text-dim">{crossCaseInsights?.edgeCount ?? 0} links</p>
              </button>
            </div>
          </div>
        </div>
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
                <option key={u.id} value={u.id}>{u.full_name} ({u.email})</option>
              ))}
            </select>
            <div className="flex gap-3">
              <button onClick={() => setAssignModal(null)} className="btn-secondary flex-1">Cancel</button>
              <button onClick={handleAssign} disabled={!selectedUser} className="btn-primary flex-1">Assign</button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirm */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="glass rounded-2xl p-6 w-full max-w-md animate-slide-in-up border border-red-500/20">
            <div className="w-12 h-12 rounded-full bg-red-500/15 flex items-center justify-center mx-auto mb-4"><Trash2 className="w-6 h-6 text-red-400"/></div>
            <h2 className="text-lg font-semibold text-trace-text text-center">Delete case?</h2>
            <p className="text-sm text-trace-text-muted text-center mt-2">This will <span className="text-red-300 font-medium">permanently delete</span> <span className="text-white font-medium">“{deleteTarget.name}”</span> and all its documents, extractions, and graph data. Audited as <span className="font-mono text-xs">CASE_DELETED</span>. This cannot be undone.</p>
            <div className="mt-4 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-xs text-red-200">Postgres cascade + Neo4j orphan cleanup. Demo case <span className="font-mono">c000…0001</span> will be re-seeded on next restart if <span className="font-mono">TRACE_RESEED_DEMO=true</span>.</div>
            <div className="flex gap-3 mt-6">
              <button onClick={()=>setDeleteTarget(null)} className="btn-secondary flex-1" disabled={deleting}>Cancel</button>
              <button onClick={handleDelete} disabled={deleting} className="flex-1 bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center justify-center gap-2 disabled:opacity-50">{deleting ? <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"/> : <Trash2 className="w-4 h-4"/>} {deleting ? 'Deleting…' : 'Delete permanently'}</button>
            </div>
          </div>
        </div>
      )}

      {/* Cases Table (kept for power users) */}
      <div className="card overflow-hidden p-0">
        <div className="px-4 py-3 border-b border-trace-border flex items-center justify-between">
          <h3 className="text-sm font-semibold text-trace-text flex items-center gap-2"><FolderOpen className="w-4 h-4 text-trace-primary"/> All cases · {cases.length}</h3>
          <span className="text-xs text-trace-text-dim hidden sm:block">Tip: hover a row, assign or jump to case</span>
        </div>
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
              <tr key={c.id} className="hover:bg-trace-surface-2 transition-colors group">
                <td className="px-5 py-3">
                  <p className="text-sm font-medium text-trace-text group-hover:text-white transition-colors">{c.name}</p>
                  <p className="text-xs text-trace-text-dim truncate max-w-xs">{c.description || 'No description'}</p>
                </td>
                <td className="px-5 py-3">{statusBadge(c.status)}</td>
                <td className="px-5 py-3 text-sm text-trace-text-dim">
                  <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {new Date(c.created_at).toLocaleDateString()}</span>
                </td>
                <td className="px-5 py-3 text-right">
                  <div className="flex items-center justify-end gap-1">
                    <button onClick={() => setAssignModal(c.id)} className="btn-secondary py-1 px-3 text-xs flex items-center gap-1">
                      <Users className="w-3 h-3" /> Assign
                    </button>
                    <button onClick={()=>navigate(`/dashboard/cases/${c.id}`)} className="p-1.5 rounded-lg hover:bg-trace-surface-3 text-trace-text-dim hover:text-trace-text"><Eye className="w-4 h-4"/></button>
                    <button onClick={()=>setDeleteTarget(c)} title="Delete case" className="p-1.5 rounded-lg hover:bg-red-500/10 text-trace-text-dim hover:text-red-400 transition-colors"><Trash2 className="w-4 h-4"/></button>
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
