/**
 * TRACE — Deep Analysis Panel
 * Community coloring, centrality sizing, bridge highlighting, cross-case recurrence, path explorer.
 * Deterministic topology only — neutral language.
 */
import { useEffect, useState } from 'react';
import api from '../lib/api';
import { X, Layers, Activity, GitBranch, Repeat, Route } from 'lucide-react';

const COMMUNITY_COLORS = [
  '#38bdf8', '#a78bfa', '#34d399', '#fb923c', '#fb7185', '#fbbf24', '#818cf8', '#f472b6',
  '#2dd4bf', '#facc15', '#e879f9', '#60a5fa',
];
const CENTRALITY_OPTIONS = [
  { value: 'betweenness', label: 'Betweenness' },
  { value: 'closeness', label: 'Closeness' },
  { value: 'eigenvector', label: 'Eigenvector' },
  { value: 'degree', label: 'Degree' },
];

export default function DeepAnalysisPanel({ caseId, cyRef, nodes, onClose }) {
  const [deep, setDeep] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [metric, setMetric] = useState('betweenness');
  const [bridgeOn, setBridgeOn] = useState(false);
  const [communityOn, setCommunityOn] = useState(false);
  const [recurrence, setRecurrence] = useState(null);
  const [pathFrom, setPathFrom] = useState('');
  const [pathTo, setPathTo] = useState('');
  const [maxHops, setMaxHops] = useState(4);
  const [paths, setPaths] = useState([]);
  const [pathError, setPathError] = useState('');
  const [pathLoading, setPathLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');
    api.get(`/api/cases/${caseId}/analysis/deep`).then(({ data }) => {
      if (!cancelled) setDeep(data);
    }).catch(err => {
      if (!cancelled) setError(err.response?.data?.detail || 'Failed to load deep analysis');
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    api.get(`/api/cases/${caseId}/analysis/cross-case-recurrence`).then(({ data }) => {
      if (!cancelled) setRecurrence(data);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [caseId]);

  // Community coloring
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || !deep) return;
    if (communityOn) {
      const map = deep.node_community || {};
      cy.nodes().forEach(n => {
        const cid = map[n.id()];
        if (cid !== undefined) n.data('community', cid);
      });
      // Apply style: override background-color via data community
      cy.nodes().forEach(n => {
        const cid = n.data('community');
        if (cid !== undefined) {
          const col = COMMUNITY_COLORS[cid % COMMUNITY_COLORS.length];
          n.style('background-color', col);
        }
      });
    } else {
      // Restore entity-type colors via removing style override (will fallback to stylesheet)
      cy.nodes().forEach(n => n.removeStyle('background-color'));
    }
  }, [communityOn, deep, cyRef]);

  // Centrality sizing
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || !deep) return;
    const vals = deep.centrality?.[metric];
    if (!vals) return;
    const max = Math.max(...Object.values(vals), 1) || 1;
    const min = Math.min(...Object.values(vals), 0);
    const range = max - min || 1;
    cy.nodes().forEach(n => {
      const v = vals[n.id()] ?? 0;
      const norm = (v - min) / range;
      const size = 18 + norm * 32; // 18-50px
      n.style('width', size);
      n.style('height', size);
      n.data('centralitySize', size);
    });
    // Fit after resize
    cy.resize();
  }, [metric, deep, cyRef]);

  // Bridge highlighting
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || !deep) return;
    cy.edges().removeClass('bridge-highlight');
    if (bridgeOn && deep.bridges?.length) {
      deep.bridges.forEach(b => {
        const edge = cy.edges().filter(e => {
          const s = e.data('source'), t = e.data('target');
          return (s === b.source && t === b.target) || (s === b.target && t === b.source);
        });
        edge.addClass('bridge-highlight');
      });
    }
  }, [bridgeOn, deep, cyRef]);

  const runPath = async () => {
    setPathError('');
    setPathLoading(true);
    setPaths([]);
    try {
      const { data } = await api.get(`/api/cases/${caseId}/analysis/paths`, {
        params: { from: pathFrom, to: pathTo, max_hops: maxHops },
      });
      setPaths(data.paths || []);
      // Highlight first path by default
      const cy = cyRef.current;
      if (cy && data.paths?.length) {
        const first = data.paths[0];
        cy.elements().removeClass('highlighted faded');
        const nodeSet = new Set(first.node_ids);
        cy.nodes().forEach(n => n.addClass(nodeSet.has(n.id()) ? 'highlighted' : 'faded'));
        cy.edges().forEach(e => {
          const both = nodeSet.has(e.data('source')) && nodeSet.has(e.data('target'));
          if (both) e.addClass('highlighted');
          else e.addClass('faded');
        });
        cy.animate({ fit: { eles: cy.elements('.highlighted'), padding: 70 } }, { duration: 300 });
      }
    } catch (err) {
      setPathError(err.response?.data?.detail || 'Path query failed');
    } finally {
      setPathLoading(false);
    }
  };

  const highlightPath = (p) => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass('highlighted faded');
    const nodeSet = new Set(p.node_ids);
    cy.nodes().forEach(n => n.addClass(nodeSet.has(n.id()) ? 'highlighted' : 'faded'));
    cy.edges().forEach(e => {
      const both = nodeSet.has(e.data('source')) && nodeSet.has(e.data('target'));
      if (both) e.addClass('highlighted');
      else e.addClass('faded');
    });
    cy.animate({ fit: { eles: cy.elements('.highlighted'), padding: 70 } }, { duration: 300 });
  };

  const clearHighlights = () => {
    cyRef.current?.elements().removeClass('highlighted faded bridge-highlight');
  };

  if (loading) return <div className="p-4 text-xs text-trace-text-dim">Loading deep analysis…</div>;
  if (error) return <div className="p-4 text-xs text-trace-danger">{error}</div>;
  if (!deep) return null;

  const entityOptions = (() => {
    const seen = new Map();
    for (const n of nodes) {
      const key = n.label.trim().toLowerCase();
      if (!seen.has(key)) seen.set(key, n);
    }
    return [...seen.values()].sort((a,b)=>a.label.localeCompare(b.label));
  })();

  return (
    <div className="h-full flex flex-col text-xs overflow-hidden bg-trace-surface border-l border-trace-border w-[380px] max-w-full">
      <div className="flex items-center justify-between px-3 py-2 border-b border-trace-border">
        <h3 className="font-semibold text-trace-text flex items-center gap-1.5"><Layers className="w-3.5 h-3.5 text-trace-primary"/> Deep Analysis</h3>
        <button onClick={onClose} className="p-1 text-trace-text-dim hover:text-trace-text"><X className="w-4 h-4"/></button>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {/* Communities */}
        <section>
          <h4 className="text-[11px] uppercase tracking-wider text-trace-text-dim mb-2 flex items-center gap-1"><Layers className="w-3 h-3"/> Communities ({deep.communities.length})</h4>
          <p className="text-[10px] text-trace-text-muted mb-2">Densely connected groups detected via Louvain (seed 42). Colors are structural, not risk labels.</p>
          <label className="flex items-center gap-2 mb-2 cursor-pointer">
            <input type="checkbox" checked={communityOn} onChange={e=>setCommunityOn(e.target.checked)} />
            <span>Color nodes by community</span>
          </label>
          <div className="space-y-1">
            {deep.communities.map(c=>(
              <div key={c.community_id} className="flex items-center gap-2 p-1.5 rounded bg-trace-surface-2">
                <span className="w-3 h-3 rounded-full" style={{background: COMMUNITY_COLORS[c.community_id % COMMUNITY_COLORS.length]}}/>
                <span className="flex-1">Group {c.community_id} — {c.size} nodes</span>
                <span className="text-[10px] text-trace-text-dim truncate max-w-[160px]">{c.nodes.slice(0,3).join(', ')}{c.size>3?' …':''}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Centrality */}
        <section>
          <h4 className="text-[11px] uppercase tracking-wider text-trace-text-dim mb-2 flex items-center gap-1"><Activity className="w-3 h-3"/> Centrality</h4>
          <p className="text-[10px] text-trace-text-muted mb-2">Which kind of structural importance — separate metrics, not blended.</p>
          <select value={metric} onChange={e=>setMetric(e.target.value)} className="input-field w-full py-1 text-xs">
            {CENTRALITY_OPTIONS.map(o=><option key={o.value} value={o.value}>{o.label} {deep.centrality.eigenvector_fallback && o.value==='eigenvector' ? '(fallback to degree)' : ''}</option>)}
          </select>
          <div className="mt-2 max-h-32 overflow-y-auto space-y-1">
            {Object.entries(deep.centrality[metric] || {}).sort((a,b)=>b[1]-a[1]).slice(0,6).map(([id,val])=>(
              <div key={id} className="flex justify-between p-1 rounded bg-trace-surface-2">
                <span className="truncate">{nodes.find(n=>n.id===id)?.label || id}</span>
                <span className="font-mono text-trace-accent">{val}</span>
              </div>
            ))}
          </div>
        </section>

        {/* K-core */}
        <section>
          <h4 className="text-[11px] uppercase tracking-wider text-trace-text-dim mb-2">K-Core (inner circle)</h4>
          <p className="text-[10px] text-trace-text-muted">Max core {deep.k_core.max_core} — inner circle nodes have most mutual connections.</p>
          <div className="mt-1 space-y-1">
            {Object.entries(deep.k_core.cores).sort((a,b)=>Number(b[0])-Number(a[0])).map(([lvl, ids])=>(
              <div key={lvl} className="p-1.5 rounded bg-trace-surface-2">
                <span className="font-mono text-trace-primary">k={lvl}</span> — {ids.length} nodes
                <span className="text-[10px] text-trace-text-dim ml-2 truncate">{ids.slice(0,4).join(', ')}{ids.length>4?' …':''}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Bridges */}
        <section>
          <h4 className="text-[11px] uppercase tracking-wider text-trace-text-dim mb-2 flex items-center gap-1"><GitBranch className="w-3 h-3"/> Bridges ({deep.bridges.length})</h4>
          <p className="text-[10px] text-trace-text-muted mb-2">Edge-level structural bridges — counterpart to articulation points.</p>
          <label className="flex items-center gap-2 mb-2 cursor-pointer">
            <input type="checkbox" checked={bridgeOn} onChange={e=>setBridgeOn(e.target.checked)} />
            <span>Highlight bridge edges</span>
          </label>
          {deep.bridges.length===0 ? <p className="text-trace-text-dim">No bridges — network is robustly connected.</p> :
            <div className="space-y-1 max-h-24 overflow-y-auto">
              {deep.bridges.map((b,i)=>(
                <div key={i} className="p-1 rounded bg-trace-surface-2 flex justify-between">
                  <span className="truncate">{b.source} ↔ {b.target}</span>
                </div>
              ))}
            </div>
          }
        </section>

        {/* Cross-case recurrence */}
        <section>
          <h4 className="text-[11px] uppercase tracking-wider text-trace-text-dim mb-2 flex items-center gap-1"><Repeat className="w-3 h-3"/> Cross-Case Recurrence</h4>
          {recurrence ? (
            recurrence.recurring_entities.length===0 ? <p className="text-trace-text-dim">No entities appear in multiple cases.</p> :
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {recurrence.recurring_entities.slice(0,8).map(r=>(
                <div key={r.entity_id} className="p-1.5 rounded bg-trace-surface-2">
                  <div className="flex justify-between">
                    <span className="font-medium truncate">{r.name}</span>
                    <span className="text-trace-accent font-mono">{r.case_count} cases</span>
                  </div>
                  <div className="text-[10px] text-trace-text-dim truncate">appears across {r.case_ids.length} cases</div>
                </div>
              ))}
            </div>
          ) : <p className="text-trace-text-dim">Loading…</p>}
        </section>

        {/* Path Explorer */}
        <section>
          <h4 className="text-[11px] uppercase tracking-wider text-trace-text-dim mb-2 flex items-center gap-1"><Route className="w-3 h-3"/> Path Explorer</h4>
          <p className="text-[10px] text-trace-text-muted mb-2">Deterministic multi-hop paths — no LLM, same guardrail as chat.</p>
          <div className="space-y-2">
            <select value={pathFrom} onChange={e=>setPathFrom(e.target.value)} className="input-field w-full py-1 text-xs">
              <option value="">From…</option>
              {entityOptions.map(n=><option key={n.id} value={n.id}>{n.label} ({n.entity_type})</option>)}
            </select>
            <select value={pathTo} onChange={e=>setPathTo(e.target.value)} className="input-field w-full py-1 text-xs">
              <option value="">To…</option>
              {entityOptions.map(n=><option key={n.id} value={n.id}>{n.label} ({n.entity_type})</option>)}
            </select>
            <div className="flex items-center gap-2">
              <label className="text-[10px]">Max hops</label>
              <input type="number" min={1} max={6} value={maxHops} onChange={e=>setMaxHops(Number(e.target.value))} className="input-field w-16 py-1 text-xs" />
              <button onClick={runPath} disabled={!pathFrom||!pathTo||pathLoading} className="btn-primary py-1 px-3 text-xs flex-1">Find paths</button>
            </div>
            {pathError && <p className="text-trace-danger">{pathError}</p>}
            {paths.length>0 && (
              <div className="space-y-2">
                <p className="text-[10px] text-trace-accent">{paths.length} path(s) found</p>
                {paths.map((p,i)=>(
                  <button key={i} onClick={()=>highlightPath(p)} className="w-full text-left p-2 rounded bg-trace-surface-2 hover:bg-trace-surface-3">
                    <div className="font-mono text-[11px]">{p.hops} hops: {p.node_names.join(' → ')}</div>
                    <div className="text-[10px] text-trace-text-dim">{p.rels.join(' → ')}</div>
                  </button>
                ))}
                <button onClick={clearHighlights} className="btn-secondary w-full py-1 text-xs">Clear highlight</button>
              </div>
            )}
            {paths.length===0 && !pathLoading && !pathError && <p className="text-trace-text-dim">No paths yet — select two entities.</p>}
          </div>
        </section>
      </div>
    </div>
  );
}
