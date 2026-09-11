/**
 * TRACE — Case Network Graph (FIR-level) — Clean, Navigable
 * Nodes = cases, edges = shared entities.
 * Fixes clutter: high-repulsion cose, concentric option, edge fade, label threshold.
 * Adds pull-slide navigator: bottom sheet + zoom slider + minimap + threshold slider.
 */
import { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import cytoscape from 'cytoscape';
import api from '../lib/api';
import {
  Network, RefreshCw, Search, X, Filter, ArrowRight,
  ZoomIn, ZoomOut, Maximize2, Layers, Grid3X3, Circle, Move
} from 'lucide-react';

const STATUS_COLORS = { open: '#38bdf8', closed: '#94a3b8', archived: '#64748b' };

function cyStyle() {
  return [
    {
      selector: 'node',
      style: {
        'background-color': (ele) => STATUS_COLORS[ele.data('status')] || '#38bdf8',
        label: 'data(label)',
        color: '#e2e8f0',
        'font-size': 11,
        'text-valign': 'bottom',
        'text-margin-y': 8,
        'text-outline-width': 2,
        'text-outline-color': '#0d1321',
        'text-max-width': 140,
        'text-wrap': 'ellipsis',
        width: (ele) => ele.data('size') || 36,
        height: (ele) => ele.data('size') || 36,
        'border-width': 2,
        'border-color': '#1e2d44',
        'overlay-opacity': 0,
      },
    },
    {
      selector: 'edge',
      style: {
        width: (ele) => Math.max(1.8, Math.min(9, 1.2 + ele.data('sharedCount') * 1.4)),
        'line-color': (ele) => {
          const c = ele.data('sharedCount') || 1;
          if (c >= 5) return '#f59e0b';
          if (c >= 3) return '#60a5fa';
          return '#475569';
        },
        'target-arrow-shape': 'none',
        'curve-style': 'bezier',
        'control-point-step-size': 50,
        opacity: (ele) => Math.min(0.9, 0.35 + ele.data('sharedCount') * 0.14),
        label: (ele) => (ele.data('sharedCount') >= 3 ? `${ele.data('sharedCount')} shared` : ''),
        'font-size': 9,
        color: '#e2e8f0',
        'text-background-color': '#0d1321',
        'text-background-opacity': 0.85,
        'text-background-padding': 4,
        'text-border-opacity': 0,
      },
    },
    {
      selector: 'edge.hover',
      style: { opacity: 1, width: 5, 'line-color': '#f59e0b', label: (ele) => `${ele.data('sharedCount')} shared` },
    },
    { selector: 'edge.highlighted', style: { width: 5, 'line-color': '#f59e0b', opacity: 1, 'z-index': 10 } },
    { selector: 'node.highlighted', style: { 'border-width': 3, 'border-color': '#f59e0b', 'overlay-color': '#f59e0b', 'overlay-opacity': 0.12 } },
    { selector: 'node.faded, edge.faded', style: { opacity: 0.08 } },
    { selector: 'node:selected', style: { 'border-width': 3, 'border-color': '#fff' } },
  ];
}

function cyElements(nodes, edges) {
  return [
    ...nodes.map((n) => ({
      data: {
        id: n.id,
        label: n.title.length > 28 ? n.title.slice(0, 28) + '…' : n.title,
        fullLabel: n.title,
        status: n.status,
        size: Math.max(32, Math.min(62, 32 + Math.sqrt(n.entity_count) * 4.5)),
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
  const [threshold, setThreshold] = useState(2); // default 2+ to reduce clutter
  const [layout, setLayout] = useState('cose');
  const [search, setSearch] = useState('');
  const [zoom, setZoom] = useState(1);
  const [selectedEdge, setSelectedEdge] = useState(null);
  const [edgeDetail, setEdgeDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [showLabels, setShowLabels] = useState(true);
  const [pullHeight, setPullHeight] = useState(0); // 0 = collapsed, 1 = expanded
  const pullRef = useRef(null);

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
    return { nodes: data.nodes, edges: data.edges.filter((e) => e.shared_count >= t) };
  }, [data, threshold]);

  const filteredElements = useMemo(() => cyElements(filtered.nodes, filtered.edges), [filtered.nodes, filtered.edges]);

  // Cytoscape lifecycle
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
          wheelSensitivity: 0.2,
          motionBlur: true,
          minZoom: 0.3,
          maxZoom: 3,
        });
        cyRef.current.on('tap', 'node', (evt) => navigate(`/dashboard/cases/${evt.target.id()}/graph`));
        cyRef.current.on('tap', 'edge', (evt) => {
          const e = evt.target.data();
          setSelectedEdge({ source: e.source, target: e.target, sharedCount: e.sharedCount, sharedEntities: e.sharedEntities });
          setDetailLoading(true); setEdgeDetail(null);
          api.get('/api/analysis/case-network/edge', { params: { case_a: e.source, case_b: e.target } })
            .then(({ data }) => setEdgeDetail(data))
            .catch(() => setEdgeDetail({ shared_entities: e.sharedEntities, count: e.sharedCount }))
            .finally(() => setDetailLoading(false));
          cyRef.current.elements().removeClass('highlighted faded');
          evt.target.addClass('highlighted');
        });
        cyRef.current.on('tap', (evt) => {
          if (evt.target === cyRef.current) {
            setSelectedEdge(null); setEdgeDetail(null);
            cyRef.current.elements().removeClass('highlighted faded hover');
          }
        });
        cyRef.current.on('mouseover', 'edge', (evt) => evt.target.addClass('hover'));
        cyRef.current.on('mouseout', 'edge', (evt) => evt.target.removeClass('hover'));
        cyRef.current.on('zoom', () => setZoom(Number(cyRef.current.zoom().toFixed(2))));
        window.__traceCaseCy = cyRef.current;
        if (filteredElements.length) {
          cyRef.current.json({ elements: filteredElements });
          requestAnimationFrame(() => {
            const c = cyRef.current; if (!c) return; c.resize();
            runLayout(c, layout);
          });
        }
      } catch (e) { console.error('[CaseNetwork] init error', e); }
      requestAnimationFrame(() => cyRef.current?.fit(undefined, 60));
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
    return () => { destroyed=true; cancelAnimationFrame(raf); ro?.disconnect(); if(cyRef.current){cyRef.current.destroy(); cyRef.current=null;} delete window.__traceCaseCy; };
  }, [filtered.nodes.length, loading]);

  const runLayout = (c, name) => {
    const opts = name === 'concentric'
      ? { name: 'concentric', animate: true, animationDuration: 600, fit: true, padding: 80, levelWidth: () => 2, concentric: (n) => n.degree(), minNodeSpacing: 40 }
      : name === 'circle'
      ? { name: 'circle', animate: true, animationDuration: 600, fit: true, padding: 80, rStepSize: 30 }
      : { name: 'cose', animate: true, animationDuration: 700, fit: true, padding: 70, idealEdgeLength: 180, nodeRepulsion: 18000, nodeOverlap: 30, componentSpacing: 120, gravity: 0.25, numIter: 1000 };
    const l = c.layout({ ...opts, eles: c.elements() });
    l.run();
  };

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.json({ elements: filteredElements });
    if (!showLabels) cy.edges().style('label', '');
    else cy.edges().forEach(e => e.style('label', e.data('sharedCount') >=3 ? `${e.data('sharedCount')} shared` : ''));
    const raf = requestAnimationFrame(() => {
      if (!cyRef.current) return;
      const c = cyRef.current; c.resize();
      if (!filteredElements.length) return;
      runLayout(c, layout);
      c.fit(undefined, 70);
    });
    return () => cancelAnimationFrame(raf);
  }, [filteredElements, layout, showLabels]);

  const focusSearch = () => {
    const cy = cyRef.current;
    if (!cy || !search.trim()) return;
    const q = search.trim().toLowerCase();
    const hit = cy.nodes().filter(n => n.data('label').toLowerCase().includes(q) || n.data('fullLabel').toLowerCase().includes(q));
    cy.elements().removeClass('highlighted faded');
    if (hit.length) {
      cy.elements().not(hit.union(hit.connectedEdges())).addClass('faded');
      hit.addClass('highlighted');
      cy.animate({ fit: { eles: hit, padding: 80 } }, { duration: 300 });
    }
  };

  const handleZoom = (v) => {
    setZoom(v);
    if (cyRef.current) cyRef.current.zoom(v);
  };

  // Pull-slide gesture for bottom navigator
  useEffect(() => {
    const el = pullRef.current;
    if (!el) return;
    let startY = 0, startH = pullHeight;
    const onStart = (e) => {
      startY = e.touches ? e.touches[0].clientY : e.clientY;
      startH = pullHeight;
      const move = (ev) => {
        const y = ev.touches ? ev.touches[0].clientY : ev.clientY;
        const dy = startY - y;
        const nh = Math.max(0, Math.min(1, startH + dy / 220));
        setPullHeight(nh);
      };
      const end = () => {
        window.removeEventListener('mousemove', move);
        window.removeEventListener('touchmove', move);
        window.removeEventListener('mouseup', end);
        window.removeEventListener('touchend', end);
        setPullHeight(p => (p > 0.5 ? 1 : 0));
      };
      window.addEventListener('mousemove', move);
      window.addEventListener('touchmove', move, { passive: false });
      window.addEventListener('mouseup', end);
      window.addEventListener('touchend', end);
    };
    el.addEventListener('mousedown', onStart);
    el.addEventListener('touchstart', onStart, { passive: true });
    return () => {
      el.removeEventListener('mousedown', onStart);
      el.removeEventListener('touchstart', onStart);
    };
  }, [pullHeight]);

  return (
    <div className="flex flex-col flex-1 min-h-0 h-full" style={{ minHeight: 0 }}>
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 bg-trace-surface border-b border-trace-border">
        <h2 className="text-sm font-semibold text-trace-text flex items-center gap-2">
          <Network className="w-4 h-4 text-trace-primary" /> Case Network
          <span className="text-trace-text-dim font-normal">{filtered.nodes.length} cases · {filtered.edges.length} links</span>
        </h2>
        <span className="text-[11px] text-trace-text-dim ml-2 hidden lg:inline">Shared entities across FIRs — review recommended, not a conclusion</span>
        <div className="flex items-center gap-2 ml-auto">
          <div className="relative hidden sm:block">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-trace-text-dim" />
            <input value={search} onChange={e=>setSearch(e.target.value)} onKeyDown={e=>e.key==='Enter'&&focusSearch()} placeholder="Find case..." className="input-field pl-8 py-1.5 w-40 text-xs" />
          </div>
          <button onClick={fetchNetwork} className="btn-secondary py-1.5 px-3 text-xs hidden sm:flex items-center gap-1"><RefreshCw className="w-3.5 h-3.5" /> Refresh</button>
        </div>
      </div>

      {/* Toolbar — de-clutter controls */}
      <div className="flex flex-wrap items-center gap-3 px-3 py-2 bg-trace-surface-2 border-b border-trace-border text-xs">
        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-trace-text-dim" />
          <span>Links ≥</span>
          <input type="range" min={1} max={5} step={1} value={threshold} onChange={e=>setThreshold(Number(e.target.value))} className="w-20 accent-trace-primary" />
          <span className="font-mono text-trace-accent w-6">{threshold}+</span>
        </div>
        <div className="h-4 w-px bg-trace-border hidden sm:block" />
        <div className="flex items-center gap-1">
          <button onClick={()=>setLayout('cose')} className={`px-2 py-1 rounded text-xs ${layout==='cose'?'bg-trace-primary text-white':'bg-trace-surface-3 text-trace-text-dim'}`}>Force</button>
          <button onClick={()=>setLayout('concentric')} className={`px-2 py-1 rounded text-xs ${layout==='concentric'?'bg-trace-primary text-white':'bg-trace-surface-3 text-trace-text-dim'}`}><Circle className="w-3 h-3 inline mr-1"/>Concentric</button>
          <button onClick={()=>setLayout('circle')} className={`px-2 py-1 rounded text-xs ${layout==='circle'?'bg-trace-primary text-white':'bg-trace-surface-3 text-trace-text-dim'}`}><Grid3X3 className="w-3 h-3 inline mr-1"/>Circle</button>
        </div>
        <label className="flex items-center gap-1.5 ml-2 cursor-pointer">
          <input type="checkbox" checked={showLabels} onChange={e=>setShowLabels(e.target.checked)} className="accent-trace-primary" />
          <span>Labels</span>
        </label>
        <div className="flex items-center gap-1 ml-auto">
          <button onClick={()=>handleZoom(Math.max(0.3, zoom-0.2))} className="btn-secondary p-1.5"><ZoomOut className="w-3.5 h-3.5"/></button>
          <span className="font-mono text-[11px] w-10 text-center">{Math.round(zoom*100)}%</span>
          <button onClick={()=>handleZoom(Math.min(3, zoom+0.2))} className="btn-secondary p-1.5"><ZoomIn className="w-3.5 h-3.5"/></button>
          <button onClick={()=>cyRef.current?.fit(undefined,70)} className="btn-secondary p-1.5"><Maximize2 className="w-3.5 h-3.5"/></button>
        </div>
      </div>

      <div className="flex-1 min-h-0 flex">
        <div className="flex-1 min-h-0 relative bg-trace-bg" style={{ minHeight: 480 }}>
          {loading ? (
            <div className="absolute inset-0 flex items-center justify-center"><div className="w-8 h-8 border-2 border-trace-primary border-t-transparent rounded-full animate-spin" /></div>
          ) : error ? (
            <div className="absolute inset-0 flex items-center justify-center"><p className="text-trace-danger text-sm">{error}</p></div>
          ) : filtered.nodes.length===0 ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
              <Network className="w-12 h-12 text-trace-text-dim" />
              <p className="text-trace-text-muted text-sm">No case links at this threshold</p>
              <p className="text-trace-text-dim text-xs">Pull threshold slider left or add shared entities.</p>
            </div>
          ) : (
            <>
              <div ref={containerRef} className="absolute inset-0" style={{ width:'100%', height:'100%', display:'block'}} />
              {/* Minimap hint + legend */}
              <div className="absolute bottom-3 left-3 glass rounded-lg px-3 py-2 flex flex-col gap-1.5 pointer-events-none">
                <div className="flex items-center gap-2 text-[10px] text-trace-text-muted"><span className="w-3 h-3 rounded-full" style={{background: STATUS_COLORS.open}}/>Open</div>
                <div className="flex items-center gap-2 text-[10px] text-trace-text-muted"><span className="w-4 h-0.5 rounded" style={{background:'#60a5fa'}}/> 3–4 shared</div>
                <div className="flex items-center gap-2 text-[10px] text-trace-accent"><span className="w-4 h-0.5 rounded" style={{background:'#f59e0b'}}/> 5+ shared</div>
              </div>
              <div className="absolute top-3 left-3 glass rounded-lg px-2 py-1 flex items-center gap-1.5 text-[10px] text-trace-text-dim">
                <Move className="w-3 h-3"/> Drag to pan · Scroll to zoom · Tap case to open
              </div>
            </>
          )}

          {/* Pull-slide navigator */}
          <div
            ref={pullRef}
            className="absolute bottom-0 left-0 right-0 bg-trace-surface border-t border-trace-border rounded-t-xl shadow-xl transition-all duration-200 flex flex-col"
            style={{ height: pullHeight===0 ? 34 : 220, cursor: 'ns-resize' }}
          >
            <div className="flex items-center justify-center py-2 flex-shrink-0">
              <div className="w-10 h-1 rounded bg-trace-text-dim/50" />
              <span className="ml-2 text-[10px] text-trace-text-dim hidden sm:inline">{pullHeight===0 ? 'Pull up for navigator' : 'Navigator — drag to slide'}</span>
            </div>
            {pullHeight>0 && (
              <div className="flex-1 min-h-0 p-3 grid grid-cols-1 lg:grid-cols-3 gap-3 overflow-y-auto">
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-trace-text flex items-center gap-1"><Layers className="w-3 h-3 text-trace-primary"/> Navigator</h4>
                  <div className="space-y-2">
                    <label className="text-[11px] text-trace-text-dim">Zoom — pull slider to zoom</label>
                    <input type="range" min={0.4} max={2.5} step={0.1} value={zoom} onChange={e=>handleZoom(Number(e.target.value))} className="w-full accent-trace-primary" />
                    <div className="flex gap-1">
                      <button onClick={()=>cyRef.current?.fit(undefined,80)} className="btn-secondary flex-1 py-1 text-xs">Fit view</button>
                      <button onClick={()=>{cyRef.current?.elements().removeClass('highlighted faded');}} className="btn-secondary flex-1 py-1 text-xs">Clear</button>
                    </div>
                  </div>
                </div>
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-trace-text">Threshold — pull to de-clutter</h4>
                  <input type="range" min={1} max={5} step={1} value={threshold} onChange={e=>setThreshold(Number(e.target.value))} className="w-full accent-trace-primary" />
                  <p className="text-[11px] text-trace-text-dim">{filtered.edges.length} links visible at ≥{threshold} shared</p>
                  <div className="flex flex-wrap gap-1">
                    {filtered.edges.slice(0,6).map(e=>(
                      <span key={e.id} className="text-[10px] px-1.5 py-0.5 rounded bg-trace-surface-2 text-trace-text-muted">{e.shared_count}×</span>
                    ))}
                  </div>
                </div>
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-trace-text">Quick filters</h4>
                  <div className="flex flex-col gap-1">
                    <button onClick={()=>setThreshold(1)} className="btn-secondary py-1 text-xs">Show all (1+)</button>
                    <button onClick={()=>setThreshold(3)} className="btn-secondary py-1 text-xs">Only strong (3+)</button>
                    <button onClick={()=>setThreshold(5)} className="btn-secondary py-1 text-xs">Only 5+ (core)</button>
                  </div>
                  <p className="text-[10px] text-trace-text-dim">Pull slider left/right to filter noise. Thickness shows strength.</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Edge drawer */}
        {selectedEdge && (
          <div className="w-[400px] max-w-full border-l border-trace-border bg-trace-surface flex flex-col">
            <div className="flex items-center justify-between px-3 py-2 border-b border-trace-border">
              <h3 className="text-xs font-semibold text-trace-text">Shared entities — review recommended</h3>
              <button onClick={()=>{setSelectedEdge(null); setEdgeDetail(null);}} className="p-1 text-trace-text-dim hover:text-trace-text"><X className="w-4 h-4"/></button>
            </div>
            <div className="px-3 py-2 border-b border-trace-border text-xs">
              <div className="flex items-center gap-1 text-trace-text-dim">
                <span className="truncate">{filtered.nodes.find(n=>n.id===selectedEdge.source)?.title || selectedEdge.source.slice(0,8)}</span>
                <ArrowRight className="w-3 h-3 flex-shrink-0" />
                <span className="truncate">{filtered.nodes.find(n=>n.id===selectedEdge.target)?.title || selectedEdge.target.slice(0,8)}</span>
              </div>
              <p className="text-trace-accent mt-1">{selectedEdge.sharedCount} shared {selectedEdge.sharedCount===1?'entity':'entities'} — factual overlap, not a linkage conclusion.</p>
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
                                {provs.slice(0,2).map(p=>(
                                  <p key={p.provenance_id} className="text-[10px] text-trace-text-muted truncate">📄 {p.filename} p.{p.page} ¶{p.paragraph} — "{p.snippet.slice(0,70)}…"</p>
                                ))}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-[10px] text-trace-text-dim mt-1">Provenance in extraction_log.</p>
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
