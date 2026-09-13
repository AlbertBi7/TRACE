/**
 * TRACE — Case Detail Page
 * Overview of a single case with documents panel, graph explorer link, and closure dossier.
 */

import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../lib/api';
import {
  ArrowLeft, FileText, Upload, Network, Users, Clock,
  ChevronRight, File, FileSpreadsheet, FileJson, GitMerge,
  Lock, Unlock, Scale, ShieldAlert, Search, AlertTriangle, CheckCircle2, X, Trash2
} from 'lucide-react';

const fileIcons = {
  pdf: FileText,
  txt: File,
  csv: FileSpreadsheet,
  json: FileJson,
};

export default function CaseDetailPage() {
  const { caseId } = useParams();
  const navigate = useNavigate();
  const [caseData, setCaseData] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [actionError, setActionError] = useState('');
  const [actionNotice, setActionNotice] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [merges, setMerges] = useState({ suggested: [], accepted: [], undone: [] });
  const [extractingId, setExtractingId] = useState(null);
  const [suggesting, setSuggesting] = useState(false);
  const [decidingMergeId, setDecidingMergeId] = useState(null);
  const [showCloseConfirm, setShowCloseConfirm] = useState(false);
  const [closing, setClosing] = useState(false);
  const [closureReport, setClosureReport] = useState(null);
  const [showClosure, setShowClosure] = useState(false);
  const [selectedCulprits, setSelectedCulprits] = useState([]);
  const [chargesInput, setChargesInput] = useState('');
  const [closureNotes, setClosureNotes] = useState('');
  const [suspectsForClosure, setSuspectsForClosure] = useState([]);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deletingCase, setDeletingCase] = useState(false);
  const [deleteCodeDetail, setDeleteCodeDetail] = useState('');
  const fileInputRef = useRef(null);

  const fetchCase = async () => {
    try {
      const [caseRes, docsRes, assignRes] = await Promise.all([
        api.get(`/api/cases/${caseId}`),
        api.get(`/api/cases/${caseId}/documents`).catch(() => ({ data: [] })),
        api.get(`/api/cases/${caseId}/assignments`).catch(() => ({ data: [] })),
      ]);
      setCaseData(caseRes.data);
      setDocuments(docsRes.data);
      setAssignments(assignRes.data);
    } catch (err) {
      console.error('Failed to load case:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchMerges = async () => {
    try {
      const { data } = await api.get(`/api/cases/${caseId}/resolution/merges`);
      setMerges(data);
    } catch { /* resolution optional until data exists */ }
  };

  useEffect(() => {
    fetchCase();
    fetchMerges();
  }, [caseId]);

  const fetchClosureReport = async (closedCase) => {
    try {
      const [graphRes, structRes, prioRes, heurRes] = await Promise.allSettled([
        api.get(`/api/cases/${caseId}/graph`).catch(() => ({ data: { nodes: [], edges: [] } })),
        api.get(`/api/cases/${caseId}/analysis/structure`).catch(() => ({ data: {} })),
        api.get(`/api/cases/${caseId}/priority-scores`).catch(() => ({ data: { scores: [] } })),
        api.get(`/api/cases/${caseId}/heuristic-links`).catch(() => ({ data: { edges: [] } })),
      ]);
      const graph = graphRes.status === 'fulfilled' ? graphRes.value.data : { nodes: [], edges: [] };
      const structure = structRes.status === 'fulfilled' ? structRes.value.data : {};
      const priorities = prioRes.status === 'fulfilled' ? prioRes.value.data : { scores: [] };
      const heuristics = heurRes.status === 'fulfilled' ? heurRes.value.data : { edges: [] };
      const suspects = (graph.nodes || []).filter(n => n.entity_type === 'PERSON').sort((a,b)=>a.label.localeCompare(b.label));
      const charges = (graph.edges || []).reduce((acc,e)=>{
        const k = e.relation || 'ASSOCIATED_WITH';
        acc[k] = (acc[k]||0)+1;
        return acc;
      }, {});
      return {
        case: closedCase,
        documents,
        assignments,
        graph,
        structure,
        priorities: (priorities.scores||[]).slice(0,5),
        heuristics: heuristics.edges||[],
        suspects,
        charges,
        generatedAt: new Date().toISOString(),
      };
    } catch (e) {
      return {
        case: closedCase,
        documents,
        assignments,
        graph: { nodes: [], edges: [] },
        suspects: [],
        charges: {},
        generatedAt: new Date().toISOString(),
        error: e.message
      };
    }
  };

  const handleCloseToggle = async () => {
    if (!caseData) return;
    const isOpen = caseData.status === 'open';
    if (isOpen) {
      // Pre-load suspects for culprit selection
      try {
        const { data: graph } = await api.get(`/api/cases/${caseId}/graph`);
        const suspects = (graph.nodes || []).filter(n => n.entity_type === 'PERSON');
        setSuspectsForClosure(suspects);
        // Pre-fill if case already had culprits (e.g., draft)
        if (caseData.culprit_entity_ids?.length) setSelectedCulprits(caseData.culprit_entity_ids);
        if (caseData.charges?.length) setChargesInput(caseData.charges.join('\n'));
        if (caseData.closure_notes) setClosureNotes(caseData.closure_notes);
      } catch {
        setSuspectsForClosure([]);
      }
      setShowCloseConfirm(true);
      return;
    }
    // Reopen
    setClosing(true);
    setActionError('');
    try {
      const { data } = await api.patch(`/api/cases/${caseId}`, { status: 'open' });
      setCaseData(data);
      setActionNotice('Case reopened. You can continue adding evidence.');
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to reopen case');
    } finally {
      setClosing(false);
    }
  };

  const confirmClose = async () => {
    setClosing(true);
    setActionError('');
    try {
      const charges = chargesInput.split('\n').map(s=>s.trim()).filter(Boolean);
      // Fallback: also split by comma if single line contains commas
      const finalCharges = charges.length === 1 && charges[0].includes(',') ? charges[0].split(',').map(s=>s.trim()).filter(Boolean) : charges;
      const payload = {
        status: 'closed',
        culprit_entity_ids: selectedCulprits,
        charges: finalCharges,
        closure_notes: closureNotes.trim(),
      };
      const { data: closed } = await api.patch(`/api/cases/${caseId}`, payload);
      setCaseData(closed);
      setShowCloseConfirm(false);
      const report = await fetchClosureReport(closed);
      // Overlay human-finalized data for immediate dossier view
      report.finalCulprits = selectedCulprits;
      report.finalCharges = finalCharges;
      report.closureNotes = closureNotes.trim();
      setClosureReport(report);
      setShowClosure(true);
      setActionNotice(`Case closed — ${selectedCulprits.length} culprit(s) finalized, ${finalCharges.length} charge(s) recorded.`);
      // Reset form
      setSelectedCulprits([]);
      setChargesInput('');
      setClosureNotes('');
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to close case');
      // keep modal open for retry
    } finally {
      setClosing(false);
    }
  };

  const handleViewDossier = async () => {
    try {
      const report = await fetchClosureReport(caseData);
      report.finalCulprits = caseData.culprit_entity_ids || [];
      report.finalCharges = caseData.charges || [];
      report.closureNotes = caseData.closure_notes || "";
      setClosureReport(report);
      setShowClosure(true);
    } catch (e) {
      setActionError('Failed to load dossier');
    }
  };

  const handleDeleteCase = async () => {
    if (!deleteCodeDetail) {
      setActionError('Confirmation code required');
      return;
    }
    setDeletingCase(true);
    setActionError('');
    try {
      await api.delete(`/api/cases/${caseId}?code=${encodeURIComponent(deleteCodeDetail)}`, { headers: { 'X-Delete-Code': deleteCodeDetail } });
      navigate('/dashboard');
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Delete failed — admin only / bad code');
      setShowDeleteConfirm(false);
    } finally {
      setDeletingCase(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-trace-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!caseData) {
    return (
      <div className="p-6 text-center text-trace-text-muted">
        Case not found or access denied.
      </div>
    );
  }

  const statusBadge = { open: 'badge-open', closed: 'badge-closed', archived: 'badge-archived' };
  const isOpen = caseData.status === 'open';

  const handleFiles = async (fileList) => {
    if (!fileList || fileList.length === 0) return;
    setUploadError('');
    setUploading(true);
    try {
      for (const f of fileList) {
        const fd = new FormData();
        fd.append('file', f);
        await api.post(`/api/cases/${caseId}/documents`, fd, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
      }
      fetchCase();
    } catch (err) {
      setUploadError(err.response?.data?.detail || 'Upload failed. Please try again.');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const decideMerge = async (mergeId, action) => {
    setActionError('');
    setActionNotice('');
    setDecidingMergeId(mergeId);
    try {
      await api.post(`/api/cases/${caseId}/resolution/merges/${mergeId}/${action}`);
      await fetchMerges();
      try {
        await api.post(`/api/cases/${caseId}/graph/sync`);
        setActionNotice(action === 'accept' ? 'Merge accepted and graph synced.' : 'Merge dismissed and graph synced.');
      } catch (syncErr) {
        setActionNotice(action === 'accept'
          ? 'Merge accepted. Sync the graph before reviewing the updated links.'
          : 'Merge dismissed. Sync the graph before reviewing the updated links.');
        setActionError(syncErr.response?.data?.detail || 'Graph sync failed');
      }
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to update merge');
    } finally {
      setDecidingMergeId(null);
    }
  };

  const runSuggest = async () => {
    setActionError('');
    setActionNotice('');
    setSuggesting(true);
    try {
      await api.post(`/api/cases/${caseId}/resolution/suggest`);
      await fetchMerges();
      setActionNotice('Match suggestions refreshed. Review each candidate before accepting.');
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Suggestion run failed');
    } finally {
      setSuggesting(false);
    }
  };

  const handleExtract = async (docId) => {
    setActionError('');
    setActionNotice('');
    setExtractingId(docId);
    try {
      await api.post(`/api/cases/${caseId}/documents/${docId}/extract`, {});
      await fetchCase();
      setActionNotice('Extraction complete. Review matches before syncing the graph.');
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Extraction failed');
    } finally {
      setExtractingId(null);
      fetchMerges();
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto animate-fade-in">
      {/* Back + Header */}
      <button onClick={() => navigate(-1)} className="flex items-center gap-1 text-sm text-trace-text-muted hover:text-trace-text mb-4 transition-colors">
        <ArrowLeft className="w-4 h-4" /> Back to Cases
      </button>

      <div className="flex items-start justify-between mb-8 gap-4">
        <div>
          <div className="flex items-center gap-3 mb-1 flex-wrap">
            <h1 className="text-2xl font-bold text-trace-text">{caseData.name}</h1>
            <span className={statusBadge[caseData.status]}>{caseData.status}</span>
            {!isOpen && <span className="text-xs px-2 py-1 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30 flex items-center gap-1"><Lock className="w-3 h-3"/> Closed</span>}
          </div>
          <p className="text-trace-text-muted text-sm">{caseData.description || 'No description'}</p>
          <div className="flex items-center gap-4 mt-2 text-xs text-trace-text-dim">
            <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> Created {new Date(caseData.created_at).toLocaleDateString()}</span>
            {caseData.status === 'closed' && <span className="flex items-center gap-1 text-amber-300">· Closed dossier available</span>}
          </div>
          {caseData.status === 'closed' && (caseData.culprit_entity_ids?.length || caseData.charges?.length || caseData.closure_notes) && (
            <div className="mt-3 p-3 rounded-xl bg-gradient-to-r from-red-500/10 to-amber-500/10 border border-red-500/20 flex flex-wrap gap-3 text-xs">
              {caseData.culprit_entity_ids?.length ? <span className="flex items-center gap-1.5"><ShieldAlert className="w-3 h-3 text-red-400"/> Culprit(s): <span className="font-medium text-red-200">{caseData.culprit_entity_ids.join(', ')}</span></span> : null}
              {caseData.charges?.length ? <span className="flex items-center gap-1.5"><Scale className="w-3 h-3 text-amber-400"/> Charges: <span className="font-mono text-amber-200">{caseData.charges.join(' | ')}</span></span> : null}
              {caseData.closure_notes ? <span className="text-trace-text-muted truncate max-w-[40ch]">“{caseData.closure_notes}”</span> : null}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
          <button
            onClick={() => navigate(`/dashboard/cases/${caseId}/graph`)}
            className="btn-secondary flex items-center gap-2"
          >
            <Network className="w-4 h-4" />
            Open Graph Explorer
          </button>
          {!isOpen && (
            <button onClick={handleViewDossier} className="btn-secondary flex items-center gap-2 border-amber-500/30 text-amber-300 hover:bg-amber-500/10">
              <FileText className="w-4 h-4"/> View Dossier
            </button>
          )}
          <button
            onClick={handleCloseToggle}
            disabled={closing}
            className={`${isOpen ? 'bg-amber-600 hover:bg-amber-500 text-white' : 'bg-emerald-600 hover:bg-emerald-500 text-white'} px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors disabled:opacity-50`}
          >
            {isOpen ? <><Lock className="w-4 h-4"/> Close Case</> : <><Unlock className="w-4 h-4"/> Reopen Case</>}
          </button>
          <button onClick={()=>{setDeleteCodeDetail(''); setShowDeleteConfirm(true)}} title="Delete case (admin) — requires code 24227" className="p-2.5 rounded-xl hover:bg-red-500/10 text-trace-text-dim hover:text-red-400 border border-transparent hover:border-red-500/20 transition-colors">
            <Trash2 className="w-4 h-4"/>
          </button>
        </div>
      </div>

      {(actionError || actionNotice) && (
        <div className={`mb-4 p-3 rounded-lg text-sm border ${actionError ? 'bg-red-500/10 border-red-500/20 text-red-300' : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'}`}>
          {actionError || actionNotice}
        </div>
      )}

      {/* Close Confirm Modal — finalize culprit & charges */}
      {showCloseConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="glass rounded-2xl p-6 w-full max-w-xl max-h-[90vh] overflow-y-auto animate-slide-in-up">
            <div className="w-12 h-12 rounded-full bg-amber-500/15 flex items-center justify-center mx-auto mb-3"><ShieldAlert className="w-6 h-6 text-amber-400"/></div>
            <h2 className="text-lg font-semibold text-trace-text text-center">Finalize closure — who is the culprit?</h2>
            <p className="text-sm text-trace-text-muted text-center mt-1">Lock <span className="text-trace-text font-medium">{caseData.name}</span> and attest culprit(s) + charges. Human decision, system records it. Reopenable.</p>

            {/* Culprit selector */}
            <div className="mt-5">
              <label className="text-xs font-semibold text-trace-text uppercase tracking-wider flex items-center gap-1.5"><Users className="w-3.5 h-3.5 text-violet-400"/> Finalized Culprit(s) — select from graph PERSONs</label>
              <p className="text-[11px] text-trace-text-dim mt-1">Tick the person(s) you are finalizing as culprit. Leave empty if under investigation. This is attestation, not auto-inference.</p>
              <div className="mt-2 card p-3 max-h-36 overflow-y-auto">
                {suspectsForClosure.length ? (
                  <div className="space-y-1.5">
                    {suspectsForClosure.map(s=>(
                      <label key={s.id} className="flex items-center gap-2 p-2 rounded-lg hover:bg-trace-surface-3 cursor-pointer border border-transparent has-[input:checked]:border-violet-500/30 has-[input:checked]:bg-violet-500/10">
                        <input type="checkbox" checked={selectedCulprits.includes(s.id)} onChange={e=>{
                          setSelectedCulprits(prev=> e.target.checked ? [...prev, s.id] : prev.filter(id=>id!==s.id));
                        }} className="rounded text-violet-600"/>
                        <span className="text-sm font-medium text-trace-text flex-1 truncate">{s.label}</span>
                        <span className="text-[11px] text-trace-text-dim truncate max-w-[14ch]">{(s.aliases||[]).slice(0,2).join(', ')}</span>
                        {s.case_ids?.length>1 && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-sky-500/15 text-sky-300">multi</span>}
                      </label>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-trace-text-dim text-center py-2">No PERSON entities yet — run extraction & <span className="text-trace-text">Sync graph</span> first. You can still close with charges only.</p>
                )}
              </div>
              {selectedCulprits.length >0 && <p className="text-xs text-violet-300 mt-1">{selectedCulprits.length} selected — will be recorded as finalized culprit(s).</p>}
            </div>

            {/* Charges */}
            <div className="mt-4">
              <label className="text-xs font-semibold text-trace-text uppercase tracking-wider flex items-center gap-1.5"><Scale className="w-3.5 h-3.5 text-amber-400"/> Charges to file</label>
              <p className="text-[11px] text-trace-text-dim mt-1">One per line, e.g., <span className="font-mono text-trace-text">IPC 302 - Murder</span>, <span className="font-mono text-trace-text">IPC 201 - Causing disappearance of evidence</span></p>
              <textarea value={chargesInput} onChange={e=>setChargesInput(e.target.value)} rows={3} placeholder={"IPC 302 - Murder\nIPC 201 - Destruction of evidence\nIPC 120B - Criminal conspiracy"} className="input-field w-full mt-2 text-sm font-mono"/>
              {chargesInput.trim() && <p className="text-xs text-amber-300 mt-1">{chargesInput.split('\n').filter(Boolean).length} charge(s) will be filed.</p>}
            </div>

            {/* Closure notes */}
            <div className="mt-4">
              <label className="text-xs font-semibold text-trace-text uppercase tracking-wider">Closure notes (handover)</label>
              <textarea value={closureNotes} onChange={e=>setClosureNotes(e.target.value)} rows={2} placeholder="Investigating officer remarks, chain-of-custody, next court date..." className="input-field w-full mt-2 text-sm"/>
            </div>

            <div className="mt-4 p-3 rounded-xl bg-trace-surface-2 border border-trace-border text-xs text-trace-text-dim">
              <p className="font-medium text-trace-text mb-1">Dossier will also include:</p>
              <ul className="list-disc list-inside space-y-0.5">
                <li>Full suspect roster, evidence inventory ({documents.length} docs), network metrics, priority & heuristic leads</li>
                <li>Provenance for every name/edge (file/page/para) — Postgres source of truth, Neo4j rebuildable</li>
              </ul>
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={()=>setShowCloseConfirm(false)} className="btn-secondary flex-1" disabled={closing}>Cancel</button>
              <button onClick={confirmClose} disabled={closing} className="btn-primary flex-1 bg-amber-600 hover:bg-amber-500 flex items-center justify-center gap-2">{closing ? <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"/> : <Lock className="w-4 h-4"/>} {closing ? 'Closing...' : `Close & File${selectedCulprits.length ? ` (${selectedCulprits.length})` : ''}`}</button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirm — admin hard delete, code 24227 */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="glass rounded-2xl p-6 w-full max-w-md animate-slide-in-up border border-red-500/20">
            <div className="w-12 h-12 rounded-full bg-red-500/15 flex items-center justify-center mx-auto mb-4"><Trash2 className="w-6 h-6 text-red-400"/></div>
            <h2 className="text-lg font-semibold text-trace-text text-center">Delete case permanently?</h2>
            <p className="text-sm text-trace-text-muted text-center mt-2">This will permanently delete <span className="text-white font-medium">“{caseData.name}”</span> and all its documents, extractions, and graph data. Audited as <span className="font-mono text-xs">CASE_DELETED</span>. Cannot be undone.</p>
            <div className="mt-4">
              <label className="text-xs font-medium text-trace-text">Enter confirmation code</label>
              <input value={deleteCodeDetail} onChange={e=>setDeleteCodeDetail(e.target.value)} placeholder="•••••" type="password" className="input-field mt-1 font-mono text-center tracking-widest" autoFocus />
              {deleteCodeDetail && <p className="text-xs text-trace-text-dim mt-1">Code will be verified server-side</p>}
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={()=>{setShowDeleteConfirm(false); setDeleteCodeDetail('');}} className="btn-secondary flex-1" disabled={deletingCase}>Cancel</button>
              <button onClick={handleDeleteCase} disabled={deletingCase || !deleteCodeDetail} className="flex-1 bg-red-600 hover:bg-red-500 disabled:bg-slate-700 disabled:text-slate-400 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center justify-center gap-2 disabled:opacity-50">{deletingCase ? <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"/> : <Trash2 className="w-4 h-4"/>} {deletingCase ? 'Deleting…' : 'Delete forever'}</button>
            </div>
          </div>
        </div>
      )}

      {/* Closure Dossier Modal */}
      {showClosure && closureReport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="glass rounded-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col animate-slide-in-up">
            <div className="p-6 border-b border-trace-border bg-gradient-to-r from-amber-500/10 via-violet-500/10 to-emerald-500/10">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-xl font-bold text-trace-text flex items-center gap-2"><Scale className="w-5 h-5 text-amber-400"/> Case Closed — Closure Dossier</h2>
                  <p className="text-sm text-trace-text-muted mt-1">{closureReport.case.name} · <span className="font-mono text-xs">{closureReport.case.id.slice(0,8)}</span> · Closed {new Date(closureReport.case.created_at).toLocaleDateString()} → {new Date().toLocaleDateString()}</p>
                  <p className="text-xs text-trace-text-dim mt-1">Generated {new Date(closureReport.generatedAt).toLocaleString()} · TRACE surfaces evidence; humans decide.</p>
                </div>
                <button onClick={()=>setShowClosure(false)} className="p-2 hover:bg-trace-surface-3 rounded-lg text-trace-text-dim hover:text-trace-text"><X className="w-5 h-5"/></button>
              </div>
            </div>
            <div className="overflow-y-auto p-6 space-y-6">
              {/* Case meta */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="p-3 rounded-xl bg-trace-surface-2 border border-trace-border"><p className="text-[11px] text-trace-text-dim uppercase">Status</p><p className="text-sm font-bold text-amber-300 capitalize">{closureReport.case.status}</p></div>
                <div className="p-3 rounded-xl bg-trace-surface-2 border border-trace-border"><p className="text-[11px] text-trace-text-dim uppercase">Documents</p><p className="text-sm font-bold text-trace-text">{closureReport.documents.length}</p></div>
                <div className="p-3 rounded-xl bg-trace-surface-2 border border-trace-border"><p className="text-[11px] text-trace-text-dim uppercase">Entities</p><p className="text-sm font-bold text-trace-text">{closureReport.graph.nodes?.length ?? 0} nodes</p></div>
                <div className="p-3 rounded-xl bg-trace-surface-2 border border-trace-border"><p className="text-[11px] text-trace-text-dim uppercase">Links</p><p className="text-sm font-bold text-trace-text">{closureReport.graph.edges?.length ?? 0} edges</p></div>
              </div>

              {/* Finalized Culprits & Charges — human attestation */}
              {(closureReport.case.culprit_entity_ids?.length || closureReport.finalCulprits?.length || closureReport.case.charges?.length || closureReport.finalCharges?.length || closureReport.closureNotes || closureReport.case.closure_notes) && (
                <div className="p-4 rounded-xl bg-gradient-to-r from-red-500/15 via-amber-500/15 to-violet-500/15 border border-amber-500/30">
                  <h3 className="text-sm font-bold text-trace-text flex items-center gap-2"><ShieldAlert className="w-4 h-4 text-red-400"/> Finalized Attestation — Culprit(s) & Charges Filed</h3>
                  <p className="text-xs text-trace-text-muted mt-1">Human-finalized at closure — not auto-inferred. Recorded by {closureReport.case.closed_by?.slice(0,8) || 'investigator'} on {new Date(closureReport.case.closed_at || closureReport.generatedAt).toLocaleString()}.</p>
                  <div className="mt-3 grid md:grid-cols-2 gap-3">
                    <div>
                      <p className="text-xs font-semibold text-trace-text uppercase">Culprit(s)</p>
                      <div className="mt-1 flex flex-wrap gap-1.5">
                        {(closureReport.finalCulprits?.length ? closureReport.finalCulprits : closureReport.case.culprit_entity_ids || []).map(id=>{
                          const node = (closureReport.graph.nodes||[]).find(n=>n.id===id);
                          const label = node?.label || id;
                          return <span key={id} className="px-3 py-1.5 rounded-full bg-red-500/20 text-red-200 border border-red-500/30 text-sm font-medium">{label}</span>
                        })}
                        {!((closureReport.finalCulprits?.length) || (closureReport.case.culprit_entity_ids?.length)) && <span className="text-xs text-trace-text-dim">No culprit finalized — under investigation.</span>}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-trace-text uppercase">Charges Filed</p>
                      <ul className="mt-1 space-y-1">
                        {(closureReport.finalCharges?.length ? closureReport.finalCharges : closureReport.case.charges || []).map((c,i)=>(
                          <li key={i} className="text-xs px-2.5 py-1.5 rounded-lg bg-amber-500/15 border border-amber-500/30 text-amber-200 font-mono">{c}</li>
                        ))}
                        {!((closureReport.finalCharges?.length) || (closureReport.case.charges?.length)) && <li className="text-xs text-trace-text-dim">No charges listed.</li>}
                      </ul>
                    </div>
                  </div>
                  {(closureReport.closureNotes || closureReport.case.closure_notes) && <p className="text-xs text-trace-text-muted mt-3 p-2.5 rounded-lg bg-trace-surface-2 border border-trace-border"><span className="font-medium text-trace-text">Notes:</span> {closureReport.closureNotes || closureReport.case.closure_notes}</p>}
                </div>
              )}

              {/* Suspects */}
              <div>
                <h3 className="text-sm font-semibold text-trace-text flex items-center gap-2 mb-3"><Search className="w-4 h-4 text-violet-400"/> Suspect Roster — {closureReport.suspects.length} PERSON(s)</h3>
                <div className="card p-0 overflow-hidden">
                  {closureReport.suspects.length ? (
                    <table className="w-full text-sm">
                      <thead><tr className="border-b border-trace-border text-xs text-trace-text-muted"><th className="text-left px-3 py-2">Name</th><th className="text-left px-3 py-2">Aliases</th><th className="text-left px-3 py-2">Evidence</th><th className="text-left px-3 py-2">Cross-case</th></tr></thead>
                      <tbody className="divide-y divide-trace-border">
                        {closureReport.suspects.map(s=>(
                          <tr key={s.id} className="hover:bg-trace-surface-2">
                            <td className="px-3 py-2 font-medium text-trace-text">{s.label}</td>
                            <td className="px-3 py-2 text-xs text-trace-text-dim truncate max-w-[20ch]">{(s.aliases||[]).join(', ') || '—'}</td>
                            <td className="px-3 py-2 text-xs text-trace-text-dim">{s.provenance_count ?? s.provCount ?? '—'} snippets</td>
                            <td className="px-3 py-2 text-xs">{s.case_ids?.length > 1 ? <span className="px-2 py-0.5 rounded-full bg-sky-500/15 text-sky-300 border border-sky-500/20">Multi-case</span> : <span className="text-trace-text-dim">Single</span>}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : <p className="p-4 text-sm text-trace-text-dim">No PERSON entities extracted — check OCR / extraction. Graph still shows {closureReport.graph.nodes?.length ?? 0} nodes.</p>}
                </div>
                <p className="text-[11px] text-trace-text-dim mt-2">* Roster is structural (graph topology), not a guilt determination. Every name traces to file/page/para.</p>
              </div>

              {/* Charges / Relations */}
              <div>
                <h3 className="text-sm font-semibold text-trace-text flex items-center gap-2 mb-3"><Scale className="w-4 h-4 text-amber-400"/> Charges & Evidentiary Links</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
                  {Object.entries(closureReport.charges).length ? Object.entries(closureReport.charges).map(([rel,count])=>(
                    <div key={rel} className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-center">
                      <p className="text-lg font-bold text-amber-300">{count}</p>
                      <p className="text-[11px] text-trace-text-muted uppercase tracking-wider">{rel.replaceAll('_',' ')}</p>
                    </div>
                  )) : <p className="text-sm text-trace-text-dim col-span-4">No relations extracted yet — run extraction and sync graph.</p>}
                </div>
                <div className="card p-3 max-h-40 overflow-y-auto">
                  {(closureReport.graph.edges||[]).slice(0,12).map(e=>(
                    <div key={e.id} className="flex items-center justify-between py-1.5 border-b border-trace-border/50 last:border-0 text-xs">
                      <span className="text-trace-text truncate">{e.source} <span className="text-trace-text-dim">—[{e.relation}]→</span> {e.target}</span>
                      <span className="font-mono text-trace-text-dim">{e.observations ?? 1} obs.</span>
                    </div>
                  ))}
                  {!closureReport.graph.edges?.length && <p className="text-xs text-trace-text-dim">No edges to display.</p>}
                </div>
                <p className="text-[11px] text-trace-text-dim mt-2">Case description (alleged offense): <span className="text-trace-text">{closureReport.case.description || '—'}</span></p>
              </div>

              {/* Documents + Team + Network */}
              <div className="grid md:grid-cols-2 gap-4">
                <div className="card p-4">
                  <h4 className="text-sm font-semibold text-trace-text mb-2 flex items-center gap-2"><FileText className="w-4 h-4 text-sky-400"/> Evidence Inventory · {closureReport.documents.length} files</h4>
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {closureReport.documents.map(d=>(
                      <div key={d.id} className="flex items-center gap-2 p-2 rounded-lg bg-trace-surface-2">
                        <FileText className="w-4 h-4 text-trace-primary shrink-0"/>
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-medium text-trace-text truncate">{d.filename}</p>
                          <p className="text-[11px] text-trace-text-dim">{d.page_count ?? 0} pages · {d.extraction_count ?? 0} extracted · {d.filetype}</p>
                        </div>
                      </div>
                    ))}
                    {!closureReport.documents.length && <p className="text-xs text-trace-text-dim">No documents.</p>}
                  </div>
                </div>
                <div className="space-y-4">
                  <div className="card p-4">
                    <h4 className="text-sm font-semibold text-trace-text mb-2 flex items-center gap-2"><Users className="w-4 h-4 text-emerald-400"/> Assigned Team · {closureReport.assignments.length}</h4>
                    {closureReport.assignments.map(a=>(
                      <div key={a.id} className="flex items-center gap-2 py-1">
                        <span className="w-6 h-6 rounded-full bg-trace-primary/20 flex items-center justify-center text-xs font-bold text-trace-primary">{a.full_name?.[0]}</span>
                        <span className="text-xs text-trace-text">{a.full_name} <span className="text-trace-text-dim">({a.role})</span></span>
                      </div>
                    ))}
                    {!closureReport.assignments.length && <p className="text-xs text-trace-text-dim">No team assigned.</p>}
                  </div>
                  <div className="card p-4">
                    <h4 className="text-sm font-semibold text-trace-text mb-2">Network & Priority</h4>
                    <p className="text-xs text-trace-text-muted">Nodes {closureReport.graph.nodes?.length ?? 0} · Edges {closureReport.graph.edges?.length ?? 0} · Articulation {closureReport.structure?.articulation_points?.length ?? 0}</p>
                    <div className="mt-2 space-y-1">
                      {(closureReport.priorities||[]).slice(0,3).map(p=>(
                        <div key={p.entity_id} className="flex justify-between text-xs"><span className="text-trace-text truncate">{p.name}</span><span className="font-mono text-amber-300">{p.score}</span></div>
                      ))}
                      {!closureReport.priorities?.length && <p className="text-xs text-trace-text-dim">No priority scores (sync graph first).</p>}
                    </div>
                    {closureReport.heuristics?.length ? <p className="text-[11px] text-amber-300 mt-2">{closureReport.heuristics.length} heuristic leads (unconfirmed, dashed)</p> : null}
                  </div>
                </div>
              </div>

              {/* Handover Checklist */}
              <div className="card p-4 bg-gradient-to-br from-violet-600/10 to-sky-600/10 border-violet-500/20">
                <h4 className="text-sm font-semibold text-trace-text flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-emerald-400"/> Handover Checklist (necessary artifacts)</h4>
                <ul className="mt-2 grid md:grid-cols-2 gap-2 text-xs text-trace-text-muted">
                  {[
                    'Chain of custody: raw files in /uploads + parsed_content JSON',
                    'Provenance: every node/edge/drawer snippet → file/page/para',
                    'Graph is rebuildable: POST /graph/sync is idempotent',
                    `Merges reviewed: ${merges.accepted.length} accepted, ${merges.suggested.length} pending`,
                    'Audit trail: all CASE/ DOCUMENT/ MERGE events in audit_log',
                    'Do not reopen without new evidence — status is reversible via Reopen'
                  ].map(item=> <li key={item} className="flex gap-2"><CheckCircle2 className="w-3 h-3 text-emerald-400 mt-0.5 shrink-0"/>{item}</li>)}
                </ul>
              </div>

              <div className="flex gap-3">
                <button onClick={()=>window.print()} className="btn-secondary flex-1">Print / Save PDF</button>
                <button onClick={()=>setShowClosure(false)} className="btn-primary flex-1">Done</button>
              </div>
              <p className="text-[11px] text-center text-trace-text-dim">TRACE is an explainable co-pilot — humans decide. No autonomous guilt scores.</p>
            </div>
          </div>
        </div>
      )}

      {/* Grid: Documents + Team */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Documents */}
        <div className="lg:col-span-2">
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-trace-text flex items-center gap-2">
                <FileText className="w-5 h-5 text-trace-primary" />
                Documents
              </h2>
              <span className="text-xs text-trace-text-dim">{documents.length} files</span>
            </div>

            {/* Upload area */}
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.txt,.csv,.json,.png,.jpg,.jpeg"
              multiple
              className="hidden"
              onChange={(e) => handleFiles(e.target.files)}
            />
            <div
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files); }}
              className={`border-2 border-dashed rounded-xl p-8 text-center mb-4 transition-colors cursor-pointer ${
                dragOver ? 'border-trace-primary bg-trace-primary/5' : 'border-trace-border hover:border-trace-primary/30'
              }`}
            >
              <Upload className={`w-8 h-8 mx-auto mb-2 ${dragOver ? 'text-trace-primary' : 'text-trace-text-dim'}`} />
              {uploading ? (
                <p className="text-sm text-trace-primary">Uploading and parsing…</p>
              ) : (
                <>
                  <p className="text-sm text-trace-text-muted">Drop files here or click to upload</p>
                  <p className="text-xs text-trace-text-dim mt-1">PDF, TXT, CSV, JSON, PNG/JPG — Max 50MB (scanned PDFs → OCR)</p>
                </>
              )}
            </div>
            {uploadError && (
              <p className="text-xs text-trace-danger mb-3">{uploadError}</p>
            )}

            {documents.length > 0 ? (
              <div className="space-y-2">
                {documents.map((doc) => {
                  const Icon = fileIcons[doc.filetype] || File;
                  return (
                    <div key={doc.id} className="flex items-center gap-3 p-3 rounded-lg bg-trace-surface-2 hover:bg-trace-surface-3 transition-colors">
                      <Icon className="w-5 h-5 text-trace-primary flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-trace-text truncate">{doc.filename}</p>
                        <p className="text-xs text-trace-text-dim">
                          {new Date(doc.uploaded_at).toLocaleString()}
                          {doc.page_count ? ` · ${doc.page_count} pages` : ''}
                          {doc.extraction_count ? ` · ${doc.extraction_count} extracted items` : ''}
                        </p>
                      </div>
                      {doc.extracted || doc.extraction_count > 0 ? (
                        <span className="badge-open badge">Extracted</span>
                      ) : (
                        <button
                          onClick={() => handleExtract(doc.id)}
                          className="btn-secondary py-1 px-3 text-xs"
                          disabled={extractingId===doc.id}
                        >
                          {extractingId===doc.id ? '…' : 'Extract'}
                        </button>
                      )}
                      <span className="badge bg-trace-surface-3 text-trace-text-dim border border-trace-border">{doc.filetype.toUpperCase()}</span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm text-trace-text-dim text-center py-4">No documents uploaded yet</p>
            )}
          </div>
        </div>

        {/* Team + Merge review */}
        <div className="space-y-6">
          <div className="card">
            <h2 className="text-lg font-semibold text-trace-text flex items-center gap-2 mb-4">
              <Users className="w-5 h-5 text-trace-primary" />
              Assigned Team
            </h2>
            {assignments.length > 0 ? (
              <div className="space-y-3">
                {assignments.map((a) => (
                  <div key={a.id} className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-trace-primary/20 flex items-center justify-center text-xs font-bold text-trace-primary">
                      {a.full_name?.charAt(0) || '?'}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-trace-text">{a.full_name}</p>
                      <p className="text-xs text-trace-text-dim">{a.role}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-trace-text-dim">No team assigned</p>
            )}
          </div>

          {/* Entity Resolution — investigator-in-the-loop review */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-trace-text flex items-center gap-2">
                <GitMerge className="w-5 h-5 text-trace-primary" />
                Entity Matches
              </h2>
              <button disabled={suggesting} onClick={runSuggest} className="btn-secondary py-1 px-3 text-xs">
                {suggesting ? 'Finding…' : 'Find Matches'}
              </button>
            </div>
            {(actionError || actionNotice) && (
              <p className={`text-xs mb-3 ${actionError ? 'text-trace-danger' : 'text-trace-success'}`} role="status">
                {actionError || actionNotice}
              </p>
            )}
            {merges.suggested.length === 0 && merges.accepted.length === 0 && merges.undone.length === 0 ? (
              <p className="text-sm text-trace-text-dim">
                No pending matches. Upload documents, run extraction, then click "Find Matches".
              </p>
            ) : (
              <div className="space-y-3">
                {merges.suggested.map((m) => (
                  <div key={m.id} className="p-3 rounded-lg bg-trace-surface-2 border border-trace-border">
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <p className="text-sm text-trace-text truncate">
                        {m.primary_value || m.primary_entity_id} <span className="text-trace-text-dim">≈</span> {m.merged_value || m.merged_entity_id}
                      </p>
                      <span className="text-xs text-trace-accent font-mono">{(m.confidence * 100).toFixed(0)}%</span>
                    </div>
                    <p className="text-[10px] text-trace-text-dim mb-2">
                      {m.method === 'shared_attribute' ? 'Shared phone/account reference' : 'Similar name (string distance)'}
                    </p>
                    <div className="flex gap-2">
                      <button disabled={decidingMergeId === m.id} onClick={() => decideMerge(m.id, 'accept')} className="btn-primary py-1 px-3 text-xs">{decidingMergeId === m.id ? 'Saving…' : 'Same entity'}</button>
                      <button disabled={decidingMergeId === m.id} onClick={() => decideMerge(m.id, 'dismiss')} className="btn-secondary py-1 px-3 text-xs">Dismiss</button>
                    </div>
                  </div>
                ))}
                {merges.accepted.map((m) => (
                  <div key={m.id} className="p-3 rounded-lg bg-trace-surface-2 flex items-center justify-between gap-2">
                    <p className="text-sm text-trace-text-dim truncate">
                      {m.primary_value || m.primary_entity_id} = {m.merged_value || m.merged_entity_id}
                    </p>
                    <button onClick={() => decideMerge(m.id, 'undo')} className="btn-secondary py-1 px-2 text-[10px]">Undo</button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
