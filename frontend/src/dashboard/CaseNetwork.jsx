/**
 * TRACE — Case Network Graph (FIR-level)
 * Nodes = cases, edges = shared entities (factual, provenance-backed).
 * No LLM, no guilt labels — neutral "shared entities" language.
 */
import { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import cytoscape from 'cytoscape';
import api from '../lib/api';
import { Network, RefreshCw, Search, X, Filter, ArrowRight } from 'lucide-react';

const STATUS_COLORS = {
  open: '#38bdf8',
  closed: '#94a3b8',
  archived: '#64748b',
};
const STATUS_LABEL = { open: 'Open', closed: 'Closed', archived: 'Archived' };

function cyStyle() {
  return [
    {
      selector: 'node',
      style: {
        'background-color': (ele) => STATUS_COLORS[ele.data('status')] || '#38bdf8',
        label: 'data(label)',
        color: '#e2e8f0',
        'font-size': 10,
        'text-valign': 'bottom',
        'text-margin-y': 6,
        width: (ele) => ele.data('size') || 30,
        height: (ele) => ele.data('size') || 30,
        'border-width': 1.5,
        'border-color': '#1e2d44',
        'text-outline-width': 2,
        'text-outline-color': '#0d1321',
      },
    },
    {
      selector: 'edge',
      style: {
        width: (ele) => Math.max(1.5, Math.min(6, 1 + ele.data('sharedCount') * 0.8)),
        'line-color': '#3b5b85',
        'target-arrow-color': '#3b5b85',
        'target-arrow-shape': 'none',
        'curve-style': 'bezier',
        label: (ele) => `${ele.data('sharedCount')} shared`,
        'font-size': 8,
        color: '#8896aa',
        'text-rotation': 'autorotate',
        'text-background-color': '#0d1321',
        'text-background-opacity': 0.85,
        'text-background-padding': 2,
      },
    },
    {
      selector: 'edge.highlighted',
      style: { width: 4, 'line-color': '#f59e0b', 'z-index': 10 },
    },
    {
      selector: 'node.highlighted',
      style: { 'border-width': 3, 'border-color': '#f59e0b', width: 38, height: 38 },
    },
    { selector: 'node.faded, edge.faded', style: { opacity: 0.15 } },
  ];
}

function cyElements(nodes, edges) {
  return [
    ...nodes.map((n) => ({
      data: {
        id: n.id,
        label: n.title,
        status: n.status,
        entityCount: n.entity_count,
        docCount: n.doc_count,
        // Size by entity count (structural, not risk)
        size: Math.max(28, Math.min(56, 28 + Math.sqrt(n.entity_count) * 4)),
      },
    })),
    ...edges.map((e) => ({
      data: {
        id: e.id,
        source: e.source,
        target: e.target,
        sharedCount: e.shared_count,
        sharedEntities: e.shared_entities,
      },
    })),
  ];
}

export default function CaseNetwork() {
  const navigate = useNavigate();
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const [data, setData] = useState({ nodes: [], edges: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [threshold, setThreshold] = useState(1);
  const [search, setSearch] = useState('');
  const [selectedEdge, setSelectedEdge] = useState(null);
  const [edgeDetail, setEdgeDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchNetwork = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const { data } = await api.get('/api/analysis/case-network');
      setData(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load case network');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchNetwork(); }, [fetchNetwork]);

  const filtered = useMemo(() => {
    const t = Number(threshold) || 1;
    return {
      nodes: data.nodes,
      edges: data.edges.filter((e) => e.shared_count >= t),
    };
  }, [data, threshold]);

  const filteredElements = useMemo(() => cyElements(filtered.nodes, filtered.edges), [filtered.nodes, filtered.edges]);

  // Cytoscape lifecycle (reuse proven fix)
  useEffect(() => {
    const el = containerRef.current;
    if (!el || !filtered.nodes.length) return;
    if (cyRef.current) return;
    let destroyed = false;
    const init = () => {
      if (destroyed || !el || cyRef.current) return;
      const { clientWidth: w, clientHeight: h } = el;
      if (w === 0 || h === 0) { requestAnimationFrame(init); return; }
      try {
        cyRef.current = cytoscape({
          container: el,
          style: cyStyle(),
          elements: [],
          wheelSensitivity: 0.25,
          motionBlur: true,
        });
        cyRef.current.on('tap', 'node', (evt) => {
          const id = evt.target.id();
          navigate(`/dashboard/cases/${id}/graph`);
        });
        cyRef.current.on('tap', 'edge', (evt) => {
          const e = evt.target.data();
          setSelectedEdge({ source: e.source, target: e.target, sharedCount: e.sharedCount, sharedEntities: e.sharedEntities });
          // Fetch drill-down
          setDetailLoading(true);
          setEdgeDetail(null);
          api.get('/api/analysis/case-network/edge', { params: { case_a: e.source, case_b: e.target } })
            .then(({ data }) => setEdgeDetail(data))
            .catch(() => setEdgeDetail({ shared_entities: e.sharedEntities, count: e.sharedCount }))
            .finally(() => setDetailLoading(false));
        });
        cyRef.current.on('tap', (evt) => {
          if (evt.target === cyRef.current) {
            setSelectedEdge(null);
            setEdgeDetail(null);
            cyRef.current.elements().removeClass('highlighted faded');
          }
        });
        window.__traceCaseCy = cyRef.current;
        if (filteredElements.length) {
          cyRef.current.json({ elements: filteredElements });
          requestAnimationFrame(() => {
            const c = cyRef.current; if (!c) return; c.resize();
            const layout = c.layout({ name: 'cose', animate: true, animationDuration: 500, fit: true, padding: 60, idealEdgeLength: 120, nodeRepulsion: 10000, eles: c.elements() });
            layout.run();
          });
        }
      } catch (e) { console.error('[CaseNetwork] init error', e); }
      requestAnimationFrame(() => { if (cyRef.current) { cyRef.current.resize(); cyRef.current.fit(undefined, 60); } });
    };
    const raf = requestAnimationFrame(init);
    let ro;
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(() => cyRef.current?.resize());
      ro.observe(el);
    } else {
      const fn = () => cyRef.current?.resize();
      window.addEventListener('resize', fn);
      ro = { disconnect: () => window.removeEventListener('resize', fn) };
    }
    return () => { destroyed=true; cancelAnimationFrame(raf); ro?.disconnect(); if (cyRef.current){cyRef.current.destroy(); cyRef.current=null;} delete window.__traceCaseCy; };
  }, [filtered.nodes.length, loading]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.json({ elements: filteredElements });
    const raf = requestAnimationFrame(() => {
      if (!cyRef.current) return;
      const c = cyRef.current; c.resize();
      if (!filteredElements.length) return;
      const layout = c.layout({ name: 'cose', animate: true, animationDuration: 500, fit: true, padding: 60, idealEdgeLength: 120, nodeRepulsion: 10000, eles: c.elements() });
      layout.run();
    });
    return () => cancelAnimationFrame(raf);
  }, [filteredElements]);

  const focusSearch = () => {
    const cy = cyRef.current;
    if (!cy || !search.trim()) return;
    const q = search.trim().toLowerCase();
    const hit = cy.nodes().filter(n => n.data('label').toLowerCase().includes(q));
    cy.elements().removeClass('highlighted faded');
    if (hit.length) {
      cy.elements().not(hit.union(hit.connectedEdges())).addClass('faded');
      hit.addClass('highlighted');
      cy.animate({ fit: { eles: hit, padding: 80 } }, { duration: 300 });
    }
  };

  const clearFilter = () => {
    setThreshold(1);
    setSearch('');
    cyRef.current?.elements().removeClass('highlighted faded');
  };

  return (
    <div className="flex flex-col flex-1 min-h-0 h-full" style={{ minHeight: 0 }}>
      <div className="flex items-center gap-3 px-4 py-3 bg-trace-surface border-b border-trace-border">
        <h2 className="text-sm font-semibold text-trace-text flex items-center gap-2">
          <Network className="w-4 h-4 text-trace-primary" /> Case Network
          <span className="text-trace-text-dim font-normal">{filtered.nodes.length} cases · {filtered.edges.length} links</span>
        </h2>
        <span className="text-[11px] text-trace-text-dim ml-2 hidden sm:inline">Shared entities across cases — review recommended, not a conclusion</span>
        <div className="flex items-center gap-2 ml-auto">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-trace-text-dim" />
            <input value={search} onChange={e=>setSearch(e.target.value)} onKeyDown={e=>e.key==='Enter'&&focusSearch()} placeholder="Find case..." className="input-field pl-8 py-1.5 w-44 text-xs" />
          </div>
          <button onClick={fetchNetwork} className="btn-secondary py-1.5 px-3 text-xs flex items-center gap-1"><RefreshCw className="w-3.5 h-3.5" /> Refresh</button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 px-4 py-2 bg-trace-surface-2 border-b border-trace-border text-xs">
        <span className="flex items-center gap-1"><Filter className="w-3 h-3 text-trace-text-dim"/>Show links with</span>
        <select value={threshold} onChange={e=>setThreshold(Number(e.target.value))} className="input-field py-1 px-2 w-24 text-xs">
          <option value={1}>1+ shared</option>
          <option value={2}>2+ shared</option>
          <option value={3}>3+ shared</option>
          <option value={5}>5+ shared</option>
        </select>
        <span className="text-trace-text-dim">shared entities</span>
        <button onClick={clearFilter} className="btn-secondary py-1 px-2 text-xs">Reset</button>
        <span className="ml-auto text-trace-text-dim hidden md:inline">Click case to open graph · Click link to review shared entities</span>
      </div>

      <div className="flex-1 min-h-0 flex">
        <div className="flex-1 min-h-0 relative bg-trace-bg" style={{ minHeight: 520 }}>
          {loading ? (
            <div className="absolute inset-0 flex items-center justify-center"><div className="w-8 h-8 border-2 border-trace-primary border-t-transparent rounded-full animate-spin" /></div>
          ) : error ? (
            <div className="absolute inset-0 flex items-center justify-center"><p className="text-trace-danger text-sm">{error}</p></div>
          ) : filtered.nodes.length===0 ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
              <Network className="w-12 h-12 text-trace-text-dim" />
              <p className="text-trace-text-muted text-sm">No case links at this threshold</p>
              <p className="text-trace-text-dim text-xs">Lower the filter or add shared entities across cases.</p>
            </div>
          ) : (
            <>
              <div ref={containerRef} className="absolute inset-0" style={{ width:'100%', height:'100%', display:'block'}} />
              <div className="absolute bottom-3 left-3 glass rounded-lg px-3 py-2 flex flex-col gap-1 pointer-events-none">
                <div className="flex items-center gap-2 text-[10px] text-trace-text-muted"><span className="w-3 h-3 rounded-full" style={{background: STATUS_COLORS.open}}/>Open</div>
                <div className="flex items-center gap-2 text-[10px] text-trace-text-muted"><span className="w-3 h-3 rounded-full" style={{background: STATUS_COLORS.closed}}/>Closed</div>
                <div className="flex items-center gap-2 text-[10px] text-trace-text-muted"><span className="w-3 h-3 rounded-full" style={{background: STATUS_COLORS.archived}}/>Archived</div>
                <div className="flex items-center gap-2 text-[10px] text-trace-text-muted"><span className="w-4 h-0.5 bg-trace-primary"/> thickness = shared count</div>
              </div>
            </>
          )}
        </div>

        {/* Edge drawer */}
        {selectedEdge && (
          <div className="w-[380px] max-w-full border-l border-trace-border bg-trace-surface flex flex-col">
            <div className="flex items-center justify-between px-3 py-2 border-b border-trace-border">
              <h3 className="text-xs font-semibold text-trace-text">Shared entities — review recommended</h3>
              <button onClick={()=>{setSelectedEdge(null); setEdgeDetail(null);}} className="p-1 text-trace-text-dim hover:text-trace-text"><X className="w-4 h-4"/></button>
            </div>
            <div className="px-3 py-2 border-b border-trace-border text-xs">
              <div className="flex items-center gap-1 text-trace-text-dim">
                <span className="truncate">{filtered.nodes.find(n=>n.id===selectedEdge.source)?.title || selectedEdge.source}</span>
                <ArrowRight className="w-3 h-3 flex-shrink-0" />
                <span className="truncate">{filtered.nodes.find(n=>n.id===selectedEdge.target)?.title || selectedEdge.target}</span>
              </div>
              <p className="text-trace-accent mt-1">{selectedEdge.sharedCount} shared {selectedEdge.sharedCount===1?'entity':'entities'} — factual overlap, not a case linkage conclusion.</p>
            </div>
            <div className="flex-1 overflow-y-auto p-3 space-y-3">
              {detailLoading ? <p className="text-xs text-trace-text-dim">Loading drill-down…</p> :
                edgeDetail ? (
                  <>
                    {edgeDetail.shared_entities.map(ent=>(
                      <div key={ent.entity_id} className="p-2 rounded bg-trace-surface-2">
                        <div className="flex justify-between">
                          <span className="font-medium text-trace-text truncate">{ent.name}</span>
                          <span className="text-[10px] text-trace-text-dim">{ent.type}</span>
                        </div>
                        {ent.aliases?.length>1 && <p className="text-[10px] text-trace-text-dim">Aliases: {ent.aliases.join(', ')}</p>}
                        {ent.provenance_by_case && Object.keys(ent.provenance_by_case).length>0 ? (
                          <div className="mt-2 space-y-2">
                            {Object.entries(ent.provenance_by_case).map(([cid, provs])=>(
                              <div key={cid} className="border-t border-trace-border pt-2">
                                <p className="text-[11px] font-medium text-trace-primary">Case {filtered.nodes.find(n=>n.id===cid)?.title || cid.slice(0,8)}</p>
                                {provs.slice(0,3).map(p=>(
                                  <p key={p.provenance_id} className="text-[10px] text-trace-text-muted truncate">📄 {p.filename} p.{p.page} ¶{p.paragraph} — "{p.snippet.slice(0,80)}…"</p>
                                ))}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-[10px] text-trace-text-dim mt-1">Provenance in underlying extraction_log (no document snippet for seed demo).</p>
                        )}
                      </div>
                    ))}
                  </>
                ) : (
                  <div className="space-y-2">
                    {selectedEdge.sharedEntities.map(e=>(
                      <div key={e.entity_id} className="p-2 rounded bg-trace-surface-2 flex justify-between">
                        <span className="truncate">{e.name}</span>
                        <span className="text-[10px] text-trace-text-dim">{e.type}</span>
                      </div>
                    ))}
                  </div>
                )
              }
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
