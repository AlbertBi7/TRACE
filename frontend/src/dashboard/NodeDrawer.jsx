/**
 * TRACE — Evidentiary Drawer (Milestone 7)
 * Node-click drawer: normalized metadata, resolved aliases, cross-case
 * presence, connected edges, and verbatim source snippets with
 * file + page + paragraph provenance from extraction_log.
 */

import { useEffect, useState } from 'react';
import api from '../lib/api';
import {
  X, FileText, MapPin, Users, ShieldQuestion, Link2, Hash,
} from 'lucide-react';

const TYPE_COLORS = {
  PERSON: '#38bdf8', ORG: '#a78bfa', LOCATION: '#34d399',
  PHONE: '#fb923c', VEHICLE: '#fb7185', BANK_ACCOUNT: '#fbbf24',
};

export default function NodeDrawer({ caseId, node, onClose }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');
    api
      .get(`/api/cases/${caseId}/graph/nodes/${node.id}`)
      .then(({ data }) => { if (!cancelled) setDetail(data); })
      .catch((err) => {
        if (!cancelled) setError(err.response?.data?.detail || 'Failed to load node detail');
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [caseId, node.id]);

  const color = TYPE_COLORS[node.entityType] || '#94a3b8';

  return (
    <div className="absolute top-0 right-0 h-full w-[400px] max-w-full glass border-l border-trace-border overflow-y-auto animate-slide-in-right z-20">
      <div className="sticky top-0 bg-trace-surface/95 backdrop-blur px-4 py-3 border-b border-trace-border flex items-start justify-between gap-2">
        <div className="flex items-start gap-2.5 min-w-0">
          <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: `${color}22`, border: `1px solid ${color}55` }}>
            <Hash className="w-4 h-4" style={{ color }} />
          </div>
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-trace-text truncate">{node.label}</h3>
            <p className="text-[10px] text-trace-text-dim font-mono">{node.id}</p>
          </div>
        </div>
        <button onClick={onClose} className="text-trace-text-dim hover:text-trace-text p-1">
          <X className="w-4 h-4" />
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-6 h-6 border-2 border-trace-primary border-t-transparent rounded-full animate-spin" />
        </div>
      ) : error ? (
        <p className="text-trace-danger text-xs p-4">{error}</p>
      ) : (
        <div className="p-4 space-y-5">
          {/* Cross-case flag */}
          {detail.cross_case && (
            <div className="flex items-center gap-2 p-2.5 rounded-lg bg-trace-accent/10 border border-trace-accent/20 text-xs text-trace-accent">
              <ShieldQuestion className="w-4 h-4" />
              Also appears in other cases — shown for context only
            </div>
          )}

          {/* Metadata */}
          <section>
            <h4 className="text-[10px] uppercase tracking-wider text-trace-text-dim mb-2">Entity</h4>
            <div className="p-3 rounded-lg bg-trace-surface-2 space-y-1.5 text-xs">
              <div className="flex justify-between gap-2">
                <span className="text-trace-text-dim">Type</span>
                <span style={{ color }}>{detail.entity_type.replace('_', ' ').toLowerCase()}</span>
              </div>
              <div className="flex justify-between gap-2">
                <span className="text-trace-text-dim">Cases</span>
                <span className="text-trace-text">{detail.case_ids.length} case(s)</span>
              </div>
              <div>
                <span className="text-trace-text-dim block mb-1">Resolved aliases</span>
                <div className="flex flex-wrap gap-1">
                  {detail.aliases.map((a) => (
                    <span key={a} className="px-1.5 py-0.5 rounded bg-trace-surface-3 text-trace-text-muted text-[10px]">{a}</span>
                  ))}
                </div>
              </div>
            </div>
          </section>

          {/* Connected edges */}
          <section>
            <h4 className="text-[10px] uppercase tracking-wider text-trace-text-dim mb-2 flex items-center gap-1">
              <Link2 className="w-3 h-3" /> Connections ({detail.edges.length})
            </h4>
            {detail.edges.length === 0 ? (
              <p className="text-xs text-trace-text-dim">No links in current graph</p>
            ) : (
              <div className="space-y-1.5">
                {detail.edges.map((e) => (
                  <div key={`${e.relation}-${e.other_id}`} className="flex items-center justify-between gap-2 p-2 rounded bg-trace-surface-2 text-xs">
                    <span className="truncate text-trace-text">{e.other_name}</span>
                    <span className="text-[10px] text-trace-text-dim flex-shrink-0">
                      {e.direction === 'out' ? '→' : '←'} {e.relation.replace('_', ' ').toLowerCase()}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Provenance — the evidentiary core */}
          <section>
            <h4 className="text-[10px] uppercase tracking-wider text-trace-text-dim mb-2 flex items-center gap-1">
              <FileText className="w-3 h-3" /> Source evidence ({detail.provenance.length})
            </h4>
            {detail.provenance.length === 0 ? (
              <p className="text-xs text-trace-text-dim">No source snippets recorded</p>
            ) : (
              <div className="space-y-2">
                {detail.provenance.map((p) => (
                  <div key={p.provenance_id} className="p-2.5 rounded-lg bg-trace-surface-2 border border-trace-border">
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <span className="text-[10px] text-trace-primary font-medium truncate">
                        {p.filename} · p.{p.page} · ¶{p.paragraph}
                      </span>
                      <span className="text-[10px] text-trace-text-dim flex-shrink-0">
                        {(p.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    <blockquote className="text-[11px] text-trace-text-muted italic leading-relaxed border-l-2 border-trace-border-light pl-2">
                      “{p.snippet}”
                    </blockquote>
                    <p className="text-[9px] text-trace-text-dim mt-1.5 font-mono">via {p.extractor}</p>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
