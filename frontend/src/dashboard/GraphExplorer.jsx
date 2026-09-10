/**
 * TRACE — Graph Explorer (Milestone 6)
 * Real Cytoscape.js visualization of the case knowledge graph:
 *   - Entity-type color encoding (trace entity palette)
 *   - cose / breadthfirst layouts, node-type filters, text search
 *   - Multi-hop path highlighting between two selected nodes (BFS in-page)
 *   - Evidentiary drawer on node click (Milestone 7)
 *   - Heuristic lead edges rendered dashed + "Unconfirmed" (Milestone 9)
 */

import { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import cytoscape from 'cytoscape';
import api from '../lib/api';
import NodeDrawer from './NodeDrawer';
import AnalysisPanel from './AnalysisPanel';
import {
  ArrowLeft, Network, RefreshCw, Search, X, LayoutGrid, Circle, Scissors,
} from 'lucide-react';

const ENTITY_COLORS = {
  PERSON: '#38bdf8',
  ORG: '#a78bfa',
  LOCATION: '#34d399',
  PHONE: '#fb923c',
  VEHICLE: '#fb7185',
  BANK_ACCOUNT: '#fbbf24',
};

const RELATION_LABELS = {
  CALLED: 'called',
  TRANSFERRED_TO: 'transferred to',
  TRAVELLED_WITH: 'travelled with',
  ASSOCIATED_WITH: 'associated with',
};

function cyElements(nodes, edges, heuristicEdges = []) {
  return [
    ...nodes.map((n) => ({
      data: {
        id: n.id,
        label: n.label,
        entityType: n.entity_type,
        aliases: n.aliases || [],
        inCase: n.in_case,
        provCount: n.provenance_count || 0,
      },
    })),
    ...edges.map((e) => ({
      data: {
        id: e.id,
        source: e.source,
        target: e.target,
        relation: e.relation,
        observations: e.observations || 1,
        heuristic: false,
      },
    })),
    ...heuristicEdges.map((h) => ({
      data: {
        id: `heur|${h.source}|${h.target}|${h.kind}`,
        source: h.source,
        target: h.target,
        relation: h.kind,
        score: h.score,
        heuristic: true,
      },
    })),
  ];
}

function cyStyle() {
  return [
    {
      selector: 'node',
      style: {
        'background-color': (ele) => ENTITY_COLORS[ele.data('entityType')] || '#94a3b8',
        label: 'data(label)',
        color: '#e2e8f0',
        'font-size': 9,
        'text-valign': 'bottom',
        'text-margin-y': 4,
        width: 26,
        height: 26,
        'border-width': 1,
        'border-color': '#1e2d44',
      },
    },
    {
      selector: 'node[?inCase = false]',
      style: { 'border-style': 'dashed', opacity: 0.65 },
    },
    {
      selector: 'edge',
      style: {
        width: 1.5,
        'line-color': '#3b5b85',
        'target-arrow-color': '#3b5b85',
        'target-arrow-shape': 'triangle',
        'curve-style': 'bezier',
        label: (ele) => RELATION_LABELS[ele.data('relation')] || ele.data('relation'),
        'font-size': 7,
        color: '#8896aa',
        'text-rotation': 'autorotate',
        'text-background-color': '#0d1321',
        'text-background-opacity': 0.85,
        'text-background-padding': 2,
      },
    },
    {
      selector: 'edge[?heuristic]',
      style: {
        'line-style': 'dashed',
        'line-color': '#f59e0b',
        'target-arrow-color': '#f59e0b',
        label: (ele) => `Heuristic Lead — Unconfirmed`,
        'font-size': 7,
        color: '#f59e0b',
      },
    },
    {
      selector: 'node.highlighted',
      style: { 'border-width': 3, 'border-color': '#f59e0b', width: 34, height: 34, 'z-index': 99 },
    },
    {
      selector: 'edge.highlighted',
      style: { width: 3, 'line-color': '#f59e0b', 'target-arrow-color': '#f59e0b', 'z-index': 99 },
    },
    {
      selector: 'node.faded, edge.faded',
      style: { opacity: 0.15 },
    },
  ];
}

/** BFS shortest path over the visible graph (deterministic, in-page). */
function findPathBFS(edges, sourceId, targetId, maxDepth = 4) {
  if (sourceId === targetId) return [sourceId];
  const adj = new Map();
  for (const e of edges) {
    if (!adj.has(e.source)) adj.set(e.source, []);
    if (!adj.has(e.target)) adj.set(e.target, []);
    adj.get(e.source).push(e.target);
    adj.get(e.target).push(e.source);
  }
  const prev = new Map([[sourceId, null]]);
  let frontier = [sourceId];
  for (let depth = 0; depth < maxDepth && frontier.length; depth++) {
    const next = [];
    for (const u of frontier) {
      for (const v of adj.get(u) || []) {
        if (prev.has(v)) continue;
        prev.set(v, u);
        if (v === targetId) {
          const path = [v];
          let cur = u;
          while (cur !== null) { path.unshift(cur); cur = prev.get(cur); }
          return path;
        }
        next.push(v);
      }
    }
    frontier = next;
  }
  return null;
}

export default function GraphExplorer() {
  const { caseId } = useParams();
  const navigate = useNavigate();
  const containerRef = useRef(null);
  const cyRef = useRef(null);

  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [heuristics, setHeuristics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [layoutName, setLayoutName] = useState('cose');
  const [typeFilter, setTypeFilter] = useState({});
  const [selectedNode, setSelectedNode] = useState(null);
  const [pathSel, setPathSel] = useState({ from: '', to: '' });
  const [pathResult, setPathResult] = useState(null);
  const [articulationPoints, setArticulationPoints] = useState([]);
  const [panelOpen, setPanelOpen] = useState(false);

  const presentTypes = useMemo(
    () => [...new Set(graph.nodes.map((n) => n.entity_type))].sort(),
    [graph.nodes]
  );

  useEffect(() => {
    if (!presentTypes.length) return;
    setTypeFilter((prev) => {
      const next = { ...prev };
      for (const t of presentTypes) if (!(t in next)) next[t] = true;
      return next;
    });
  }, [presentTypes]);

  const loadGraph = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const { data } = await api.get(`/api/cases/${caseId}/graph`);
      setGraph(data);
      try {
        const h = await api.get(`/api/cases/${caseId}/heuristic-links`);
        setHeuristics(h.data.edges || []);
      } catch { /* heuristics optional (Milestone 9) */ }
      try {
        const s = await api.get(`/api/cases/${caseId}/analysis/structure`);
        setArticulationPoints(s.data.articulation_points || []);
      } catch { /* structure optional */ }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load graph');
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => { loadGraph(); }, [loadGraph]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      await api.post(`/api/cases/${caseId}/graph/sync`);
      await loadGraph();
    } catch (err) {
      alert(err.response?.data?.detail || 'Sync failed');
    } finally {
      setSyncing(false);
    }
  };

  const filteredElements = useMemo(() => {
    const visible = new Set(
      graph.nodes.filter((n) => typeFilter[n.entity_type] !== false).map((n) => n.id)
    );
    return cyElements(
      graph.nodes.filter((n) => visible.has(n.id)),
      graph.edges.filter((e) => visible.has(e.source) && visible.has(e.target)),
      heuristics.filter((h) => visible.has(h.source) && visible.has(h.target))
    );
  }, [graph, heuristics, typeFilter]);

  // ─── Cytoscape lifecycle ──────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || filteredElements.length === 0) return;

    if (!cyRef.current) {
      cyRef.current = cytoscape({
        container: containerRef.current,
        style: cyStyle(),
        wheelSensitivity: 0.2,
      });
      cyRef.current.on('tap', 'node', async (evt) => {
        setSelectedNode(evt.target.data());
      });
      // Test hook: canvas-rendered nodes can't be targeted by DOM selectors,
      // so UI tests compute rendered positions via this handle.
      window.__traceCy = cyRef.current;
    }
    const cy = cyRef.current;
    cy.elements().remove();
    cy.add(filteredElements);
    cy.layout({
      name: layoutName,
      animate: true,
      animationDuration: 400,
      idealEdgeLength: 90,
      nodeRepulsion: 8000,
      padding: 40,
    }).run();

    return () => {};
  }, [filteredElements, layoutName]);

  useEffect(() => () => {
    if (cyRef.current) { cyRef.current.destroy(); cyRef.current = null; }
  }, []);

  // ─── Search focus ─────────────────────────────────────────────────
  const focusSearch = () => {
    const cy = cyRef.current;
    if (!cy || !search.trim()) return;
    const q = search.trim().toLowerCase();
    const hit = cy.nodes().filter(
      (n) =>
        n.data('label').toLowerCase().includes(q) ||
        (n.data('aliases') || []).some((a) => a.toLowerCase().includes(q))
    );
    cy.elements().removeClass('faded highlighted');
    if (hit.length) {
      cy.elements().not(hit.union(hit.connectedEdges())).addClass('faded');
      hit.addClass('highlighted');
      cy.animate({ fit: { eles: hit, padding: 80 } }, { duration: 300 });
    }
  };

  // ─── Path highlight ───────────────────────────────────────────────
  const highlightPath = () => {
    const cy = cyRef.current;
    if (!cy || !pathSel.from || !pathSel.to) return;
    const visibleEdges = cy.edges().map((e) => ({
      source: e.data('source'),
      target: e.data('target'),
    }));
    const path = findPathBFS(visibleEdges, pathSel.from, pathSel.to);
    cy.elements().removeClass('highlighted faded');
    if (!path) {
      setPathResult({ found: false, path: [] });
      return;
    }
    const nodeSet = new Set(path);
    const edgeIds = new Set();
    for (let i = 0; i < path.length - 1; i++) {
      const a = path[i], b = path[i + 1];
      cy.edges().forEach((e) => {
        const s = e.data('source'), t = e.data('target');
        if ((s === a && t === b) || (s === b && t === a)) edgeIds.add(e.id());
      });
    }
    cy.nodes().forEach((n) => {
      if (nodeSet.has(n.id())) n.addClass('highlighted');
      else n.addClass('faded');
    });
    cy.edges().forEach((e) => {
      if (edgeIds.has(e.id())) e.addClass('highlighted');
      else e.addClass('faded');
    });
    setPathResult({ found: true, hops: path.length - 1, path });
    cy.animate({ fit: { eles: cy.elements('[class~="highlighted"]'), padding: 70 } }, { duration: 300 });
  };

  const clearHighlight = () => {
    const cy = cyRef.current;
    if (cy) cy.elements().removeClass('highlighted faded');
    setPathResult(null);
  };

  // Highlight a chat path (node id list) on the canvas
  const highlightChatPath = (nodeIds) => {
    const cy = cyRef.current;
    if (!cy || !nodeIds?.length) return;
    cy.elements().removeClass('highlighted faded');
    const nodeSet = new Set(nodeIds);
    cy.nodes().forEach((n) => n.addClass(nodeSet.has(n.id()) ? 'highlighted' : 'faded'));
    cy.edges().forEach((e) => {
      const both = nodeSet.has(e.data('source')) && nodeSet.has(e.data('target'));
      const adjacent = nodeSet.has(e.data('source')) || nodeSet.has(e.data('target'));
      if (both) e.addClass('highlighted');
      else if (adjacent) e.addClass('faded');
    });
    cy.animate({ fit: { eles: cy.elements('[class~="highlighted"]'), padding: 70 } }, { duration: 300 });
  };

  // Highlight fragmented-away nodes after a removal simulation
  const highlightFragmented = (nodeIds) => {
    const cy = cyRef.current;
    if (!cy || !nodeIds?.length) return;
    cy.elements().removeClass('highlighted faded');
    nodeIds.forEach((id) => {
      const n = cy.getElementById(id);
      if (n.nonempty()) n.addClass('highlighted');
    });
  };

  const entityOptions = graph.nodes
    .filter((n) => n.entity_type === 'PERSON' || n.entity_type === 'ORG')
    .sort((a, b) => a.label.localeCompare(b.label));

  return (
    <div className="h-full flex flex-col">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3 px-4 py-3 bg-trace-surface border-b border-trace-border">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(`/dashboard/cases/${caseId}`)}
            className="flex items-center gap-1 text-sm text-trace-text-muted hover:text-trace-text transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> Back
          </button>
          <div className="w-px h-5 bg-trace-border" />
          <h2 className="text-sm font-semibold text-trace-text flex items-center gap-2">
            <Network className="w-4 h-4 text-trace-primary" />
            Graph Explorer
            <span className="text-trace-text-dim font-normal">
              {graph.nodes.length} nodes · {graph.edges.length} links
            </span>
          </h2>
        </div>

        <div className="flex items-center gap-2 ml-auto">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-trace-text-dim" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && focusSearch()}
              placeholder="Find entity…"
              className="input-field pl-8 py-1.5 w-44 text-xs"
            />
          </div>
          <button onClick={() => setLayoutName(layoutName === 'cose' ? 'breadthfirst' : 'cose')} className="btn-secondary py-1.5 px-3 text-xs flex items-center gap-1">
            <LayoutGrid className="w-3.5 h-3.5" /> {layoutName === 'cose' ? 'Force' : 'Tree'} layout
          </button>
          <button onClick={handleSync} disabled={syncing} className="btn-primary py-1.5 px-3 text-xs flex items-center gap-1">
            <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} /> Sync graph
          </button>
        </div>
      </div>

      {/* Filters + path tool */}
      <div className="flex flex-wrap items-center gap-3 px-4 py-2 bg-trace-surface-2 border-b border-trace-border text-xs">
        {presentTypes.map((t) => (
          <button
            key={t}
            onClick={() => setTypeFilter({ ...typeFilter, [t]: typeFilter[t] === false })}
            className={`flex items-center gap-1.5 px-2 py-1 rounded-full border transition-all ${
              typeFilter[t] === false
                ? 'border-trace-border text-trace-text-dim opacity-50'
                : 'border-trace-border-light text-trace-text'
            }`}
          >
            <Circle className="w-2.5 h-2.5" style={{ color: ENTITY_COLORS[t] || '#94a3b8' }} />
            {t.replace('_', ' ').toLowerCase()}
          </button>
        ))}

        <div className="flex items-center gap-1.5 ml-auto">
          <span className="text-trace-text-dim">Path:</span>
          <select
            value={pathSel.from}
            onChange={(e) => setPathSel({ ...pathSel, from: e.target.value })}
            className="input-field py-1 px-2 w-36 text-xs"
          >
            <option value="">From…</option>
            {entityOptions.map((n) => <option key={n.id} value={n.id}>{n.label}</option>)}
          </select>
          <select
            value={pathSel.to}
            onChange={(e) => setPathSel({ ...pathSel, to: e.target.value })}
            className="input-field py-1 px-2 w-36 text-xs"
          >
            <option value="">To…</option>
            {entityOptions.map((n) => <option key={n.id} value={n.id}>{n.label}</option>)}
          </select>
          <button onClick={highlightPath} className="btn-secondary py-1 px-2.5">Show path</button>
          <button onClick={clearHighlight} className="btn-secondary py-1 px-2"><X className="w-3.5 h-3.5" /></button>
          {pathResult && (
            <span className={pathResult.found ? 'text-trace-accent' : 'text-trace-text-dim'}>
              {pathResult.found ? `${pathResult.hops} hop(s)` : 'No path within 4 hops'}
            </span>
          )}
        </div>
      </div>

      {/* Canvas */}
      <div className="flex-1 relative bg-trace-bg">
        {loading ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-8 h-8 border-2 border-trace-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : error ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <p className="text-trace-danger text-sm">{error}</p>
          </div>
        ) : graph.nodes.length === 0 ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
            <Network className="w-12 h-12 text-trace-text-dim" />
            <p className="text-trace-text-muted text-sm">No graph data yet</p>
            <p className="text-trace-text-dim text-xs max-w-sm text-center">
              Upload documents, run extraction, then click <span className="text-trace-text">Sync graph</span> to build
              the network from extracted entities and links.
            </p>
          </div>
        ) : (
          <>
            <div ref={containerRef} className="absolute inset-0" />
            {/* Legend */}
            <div className="absolute bottom-3 left-3 glass rounded-lg px-3 py-2 flex flex-col gap-1 pointer-events-none">
              {Object.entries(ENTITY_COLORS).map(([t, c]) => (
                <div key={t} className="flex items-center gap-2 text-[10px] text-trace-text-muted">
                  <span className="w-2 h-2 rounded-full" style={{ background: c }} />
                  {t.replace('_', ' ').toLowerCase()}
                </div>
              ))}
              <div className="flex items-center gap-2 text-[10px] text-trace-accent">
                <span className="w-4 border-t border-dashed border-trace-accent" />
                heuristic lead — unconfirmed
              </div>
            </div>
          </>
        )}

        {/* Simulator launcher */}
        {!panelOpen && graph.nodes.length > 0 && (
          <button
            onClick={() => setPanelOpen(true)}
            className="absolute top-3 right-3 btn-secondary py-1.5 px-3 text-xs flex items-center gap-1.5"
          >
            <Scissors className="w-3.5 h-3.5" /> Analyze
          </button>
        )}

        {selectedNode && (
          <NodeDrawer
            caseId={caseId}
            node={selectedNode}
            onClose={() => setSelectedNode(null)}
          />
        )}

        {panelOpen && (
          <div className="absolute bottom-0 left-0 right-0 z-30">
            <AnalysisPanel
              caseId={caseId}
              nodes={graph.nodes}
              articulationPoints={articulationPoints}
              onHighlightPath={highlightChatPath}
              onHighlightNodes={highlightFragmented}
              onClose={() => { setPanelOpen(false); clearHighlight(); }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
