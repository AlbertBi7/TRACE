/**
 * TRACE — Case Detail Page
 * Overview of a single case with documents panel and graph explorer link.
 * Documents are uploaded and extracted through the case-scoped API.
 */

import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../lib/api';
import {
  ArrowLeft, FileText, Upload, Network, Users, Clock,
  ChevronRight, File, FileSpreadsheet, FileJson, GitMerge
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

      <div className="flex items-start justify-between mb-8">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-2xl font-bold text-trace-text">{caseData.name}</h1>
            <span className={statusBadge[caseData.status]}>{caseData.status}</span>
          </div>
          <p className="text-trace-text-muted text-sm">{caseData.description || 'No description'}</p>
          <div className="flex items-center gap-4 mt-2 text-xs text-trace-text-dim">
            <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> Created {new Date(caseData.created_at).toLocaleDateString()}</span>
          </div>
        </div>

        <button
          onClick={() => navigate(`/dashboard/cases/${caseId}/graph`)}
          className="btn-primary flex items-center gap-2"
        >
          <Network className="w-4 h-4" />
          Open Graph Explorer
        </button>
      </div>

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
              accept=".pdf,.txt,.csv,.json"
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
                  <p className="text-xs text-trace-text-dim mt-1">PDF, TXT, CSV, JSON — Max 50MB</p>
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
                        >
                          Extract
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
