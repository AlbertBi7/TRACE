/**
 * TRACE — Main Application
 * Root component with React Router, AuthContext, role-guarded routes.
 */

import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet, useNavigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Sidebar from './components/Sidebar';
import LoginPage from './auth/LoginPage';
import CaseListPage from './dashboard/CaseListPage';
import CaseDetailPage from './dashboard/CaseDetailPage';
import GraphExplorer from './dashboard/GraphExplorer';
import CaseNetwork from './dashboard/CaseNetwork';
import UserManagement from './admin/UserManagement';
import AuditLog from './admin/AuditLog';
import CaseOverview from './admin/CaseOverview';
import api from './lib/api';

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
  const [stats, setStats] = useState({ cases: [], users: [], audit: [], health: null, network: null, loading: true });
  const navigate = useNavigate();
  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([
      api.get('/api/cases').then(r => !cancelled && setStats(s => ({ ...s, cases: r.data }))),
      api.get('/api/users').then(r => !cancelled && setStats(s => ({ ...s, users: r.data }))),
      api.get('/api/audit', { params: { page: 1, page_size: 12 } }).then(r => !cancelled && setStats(s => ({ ...s, audit: r.data?.data || [] }))),
      api.get('/api/health').then(r => !cancelled && setStats(s => ({ ...s, health: r.data }))).catch(()=>{}),
      api.get('/api/analysis/case-network').then(r => !cancelled && setStats(s => ({ ...s, network: r.data }))).catch(()=>{}),
    ]).finally(()=> !cancelled && setStats(s=>({...s, loading:false})));
    return ()=>{ cancelled=true; };
  }, []);
  const kpi = (() => {
    const totalCases = stats.cases.length;
    const open = stats.cases.filter(c=>c.status==='open').length;
    const closed = stats.cases.filter(c=>c.status==='closed').length;
    const investigators = stats.users.filter(u=>u.role==='investigator' && u.is_active).length;
    const admins = stats.users.filter(u=>u.role==='admin').length;
    const recentCases = [...stats.cases].sort((a,b)=> new Date(b.created_at)-new Date(a.created_at)).slice(0,3);
    return { totalCases, open, closed, investigators, admins, recentCases };
  })();
  if (stats.loading) return <div className="flex items-center justify-center h-64"><div className="w-8 h-8 border-2 border-trace-primary border-t-transparent rounded-full animate-spin"/></div>;
  return (
    <div className="p-6 max-w-7xl mx-auto animate-fade-in space-y-6">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl border border-violet-500/20 bg-gradient-to-br from-slate-900 via-slate-900 to-violet-950/30 p-6">
        <div className="absolute -right-10 -top-10 w-48 h-48 rounded-full bg-violet-600/20 blur-3xl"/>
        <div className="absolute -left-10 -bottom-10 w-48 h-48 rounded-full bg-sky-600/15 blur-3xl"/>
        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <span className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-600/30 text-white text-sm font-bold">◈</span>
              TRACE Command Center
            </h1>
            <p className="text-slate-400 text-sm mt-1">System overview and management — live investigative pulse</p>
            <div className="flex items-center gap-2 mt-3">
              <span className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border ${stats.health?.status==='healthy'?'bg-emerald-500/10 text-emerald-300 border-emerald-500/20':'bg-amber-500/10 text-amber-300 border-amber-500/20'}`}>
                <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse"/>{stats.health?.status || 'checking'} · API
              </span>
              <span className="text-xs text-slate-500">{new Date().toLocaleDateString('en-IN', {weekday:'short', day:'numeric', month:'short'})} · {kpi.totalCases} cases</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={()=>navigate('/admin/cases')} className="px-4 py-2 rounded-xl bg-white text-slate-900 text-sm font-medium hover:bg-slate-100 transition-colors">View all cases →</button>
            <button onClick={()=>navigate('/admin/users')} className="px-4 py-2 rounded-xl bg-slate-800 text-white text-sm font-medium border border-slate-700 hover:bg-slate-700 transition-colors">Manage team</button>
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          {label:'Total Cases', value:kpi.totalCases, sub:`${kpi.open} open · ${kpi.closed} closed`, icon:'◈', grad:'from-violet-600 to-indigo-600'},
          {label:'Investigators', value:kpi.investigators, sub:`${kpi.admins} admins · ${stats.users.length} total`, icon:'◉', grad:'from-emerald-600 to-teal-600'},
          {label:'Cross-case Links', value:stats.network?.edges?.length ?? 0, sub:`${stats.network?.nodes?.length ?? kpi.totalCases} nodes in case graph`, icon:'⬢', grad:'from-sky-600 to-cyan-600'},
          {label:'Recent Events', value:stats.audit.length, sub: stats.audit[0]?.action?.replaceAll('_',' ') || 'No activity yet', icon:'◎', grad:'from-amber-600 to-orange-600'},
        ].map(card=>(
          <div key={card.label} className="card p-4 relative overflow-hidden group hover:border-violet-500/20 transition-colors">
            <div className={`absolute -right-6 -top-6 w-20 h-20 rounded-full bg-gradient-to-br ${card.grad} opacity-15 blur-2xl group-hover:opacity-25 transition-opacity`}/>
            <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${card.grad} flex items-center justify-center text-white text-sm shadow-md`}>{card.icon}</div>
            <p className="text-2xl font-bold text-trace-text mt-3">{card.value}</p>
            <p className="text-xs font-medium text-trace-text-muted">{card.label}</p>
            <p className="text-[11px] text-trace-text-dim mt-1 truncate">{card.sub}</p>
          </div>
        ))}
      </div>

      {/* Middle: status donut + quick nav */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="card p-5 lg:col-span-2">
          <h3 className="text-sm font-semibold text-trace-text mb-4">Case lifecycle</h3>
          <div className="grid grid-cols-3 gap-4">
            {[
              {k:'open', label:'Open', count:kpi.open, color:'bg-emerald-500', light:'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'},
              {k:'closed', label:'Closed', count:kpi.closed, color:'bg-amber-500', light:'bg-amber-500/15 text-amber-400 border-amber-500/30'},
              {k:'archived', label:'Archived', count:stats.cases.filter(c=>c.status==='archived').length, color:'bg-slate-500', light:'bg-slate-500/15 text-slate-400 border-slate-500/30'},
            ].map(row=>{
              const pct = kpi.totalCases ? Math.round(row.count/kpi.totalCases*100) : 0;
              return (
                <div key={row.k} className="text-center">
                  <div className="mx-auto w-20 h-20 rounded-full border-4 border-trace-surface-3 flex items-center justify-center relative" style={{background:`conic-gradient(${row.color==='bg-emerald-500'?'#10b981':row.color==='bg-amber-500'?'#f59e0b':'#64748b'} ${pct*3.6}deg, #1e293b 0deg)`}}>
                    <span className="w-14 h-14 rounded-full bg-trace-surface flex items-center justify-center text-sm font-bold text-trace-text">{pct}%</span>
                  </div>
                  <p className="text-sm font-medium text-trace-text mt-2">{row.label}</p>
                  <p className="text-xs text-trace-text-dim">{row.count} cases</p>
                </div>
              );
            })}
          </div>
          <div className="mt-5 p-3 rounded-xl bg-trace-surface-2 border border-trace-border flex items-center justify-between">
            <span className="text-xs text-trace-text-muted">Cross-case recurrence</span>
            <span className="text-xs font-mono text-sky-300">{stats.network?.edges?.length ? `${stats.network.edges[0].shared_count} shared entities (top)` : 'No recurring entities yet — upload overlapping FIRs to see links'}</span>
          </div>
        </div>

        <div className="card p-5 flex flex-col">
          <h3 className="text-sm font-semibold text-trace-text mb-3">Jump to</h3>
          <div className="grid grid-cols-1 gap-2.5">
            {[
              {title:'User Management', desc:`${kpi.investigators} investigators · ${kpi.admins} admins`, to:'/admin/users', grad:'from-violet-600 to-indigo-600'},
              {title:'All Cases', desc:`${kpi.totalCases} cases · ${kpi.open} open`, to:'/admin/cases', grad:'from-sky-600 to-cyan-600'},
              {title:'Audit Log', desc:`${stats.audit.length} recent events`, to:'/admin/audit', grad:'from-amber-600 to-orange-600'},
              {title:'Case Network', desc:'FIR-level cross-case graph', to:'/dashboard/case-network', grad:'from-emerald-600 to-teal-600'},
            ].map(item=>(
              <button key={item.to} onClick={()=>navigate(item.to)} className="text-left p-3.5 rounded-xl bg-trace-surface-2 hover:bg-trace-surface-3 border border-trace-border hover:border-violet-500/30 transition-all group">
                <div className={`w-7 h-7 rounded-lg bg-gradient-to-br ${item.grad} flex items-center justify-center text-white text-xs`}>→</div>
                <p className="text-sm font-medium text-trace-text mt-2 group-hover:text-white">{item.title}</p>
                <p className="text-xs text-trace-text-dim truncate">{item.desc}</p>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Recent cases + audit */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card p-0 overflow-hidden">
          <div className="px-4 py-3 border-b border-trace-border flex items-center justify-between">
            <h3 className="text-sm font-semibold text-trace-text">Recent cases</h3>
            <button onClick={()=>navigate('/admin/cases')} className="text-xs text-violet-400 hover:text-violet-300">View all →</button>
          </div>
          <div className="divide-y divide-trace-border">
            {kpi.recentCases.map(c=>(
              <div key={c.id} className="px-4 py-3 flex items-center justify-between hover:bg-trace-surface-2 transition-colors">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-trace-text truncate">{c.name}</p>
                  <p className="text-xs text-trace-text-dim">{new Date(c.created_at).toLocaleDateString()} · {c.status}</p>
                </div>
                <span className={`w-2 h-2 rounded-full ${c.status==='open'?'bg-emerald-500':c.status==='closed'?'bg-amber-500':'bg-slate-500'}`}/>
              </div>
            ))}
            {!kpi.recentCases.length && <p className="p-6 text-sm text-trace-text-dim text-center">No cases yet</p>}
          </div>
        </div>

        <div className="card p-0 overflow-hidden">
          <div className="px-4 py-3 border-b border-trace-border">
            <h3 className="text-sm font-semibold text-trace-text">Live audit</h3>
            <p className="text-xs text-trace-text-dim">Last {stats.audit.length} events · provenance & RBAC tracked</p>
          </div>
          <div className="divide-y divide-trace-border max-h-[220px] overflow-y-auto">
            {stats.audit.slice(0,6).map(log=>(
              <div key={log.id} className="px-4 py-2.5 flex items-center gap-3 hover:bg-trace-surface-2">
                <span className={`w-1.5 h-1.5 rounded-full ${log.action.includes('LOGIN')?'bg-emerald-500':log.action.includes('CASE')?'bg-sky-500':'bg-slate-500'}`}/>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-mono text-trace-text truncate">{log.action}</p>
                  <p className="text-[11px] text-trace-text-dim truncate">{log.user_email || 'system'} · {new Date(log.timestamp).toLocaleTimeString()}</p>
                </div>
                <span className="text-[11px] font-mono text-trace-text-dim">{log.target_type || ''}</span>
              </div>
            ))}
            {!stats.audit.length && <p className="p-6 text-sm text-trace-text-dim text-center">No audit events yet</p>}
          </div>
        </div>
      </div>

      <p className="text-[11px] text-trace-text-dim text-center">TRACE surfaces evidence and structure; humans decide. · Postgres is source of truth, Neo4j rebuildable · OCR preserves page/para</p>
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
            <Route path="/dashboard/case-network" element={<CaseNetwork />} />
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
