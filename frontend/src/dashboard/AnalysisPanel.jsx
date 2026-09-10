/**
 * TRACE — Analysis Panel (Milestones 8-11 UI)
 * Bottom panel in the Graph Explorer with three tabs:
 *   Chat        — scoped "how is X connected to Y" (SSE, cited, deterministic path)
 *   Simulation  — hypothetical node removal: before/after connectivity metrics
 *   Priority    — composite structural prioritization with explanations
 * All results are structural/neutral; the panel never asserts culpability.
 */

import { useState, useEffect, useRef } from 'react';
import {
  MessageSquare, Scissors, BarChart3, X, Send, Sparkles, AlertTriangle,
} from 'lucide-react';
import api from '../lib/api';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function useSSEChat(caseId) {
  const [messages, setMessages] = useState([]);
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef(null);

  const ask = async (question, onPath) => {
    setMessages((m) => [...m, { role: 'user', text: question }, { role: 'assistant', text: '', citations: [] }]);
    setStreaming(true);
    const token = localStorage.getItem('trace_access_token');
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const url = `${API_BASE}/api/cases/${caseId}/chat?q=${encodeURIComponent(question)}`;
      const resp = await fetch(url, { headers: { Authorization: `Bearer ${token}` }, signal: controller.signal });
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const evt = JSON.parse(line.slice(6));
          if (evt.type === 'tokens') {
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1] = { ...copy[copy.length - 1], text: copy[copy.length - 1].text + evt.text };
              return copy;
            });
          } else if (evt.type === 'citations') {
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1] = { ...copy[copy.length - 1], citations: evt.citations || [], path: evt.path };
              return copy;
            });
            if (onPath && evt.path) onPath(evt.path.node_ids);
          } else if (evt.type === 'error') {
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1] = { ...copy[copy.length - 1], text: copy[copy.length - 1].text + evt.message, isError: true };
              return copy;
            });
          }
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        setMessages((m) => [...m.slice(0, -1), { role: 'assistant', text: 'Chat request failed.', isError: true }]);
      }
    } finally {
      setStreaming(false);
    }
  };

  return { messages, streaming, ask };
}

function ChatTab({ caseId, people, onPath }) {
  const [input, setInput] = useState('');
  const { messages, streaming, ask } = useSSEChat(caseId);
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);

  const submit = (e) => {
    e.preventDefault();
    if (!input.trim() || streaming) return;
    ask(input.trim(), onPath);
    setInput('');
  };

  return (
    <div className="flex flex-col h-full">
      <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-3 p-3 text-sm">
        {messages.length === 0 && (
          <p className="text-trace-text-dim text-xs">
            Ask how two entities are connected — e.g.{" "}
            <button className="text-trace-primary hover:underline" onClick={() => setInput('How is Rohan Mehra connected to Anita Desai?')}>
              "How is Rohan Mehra connected to Anita Desai?"
            </button>
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === 'user' ? 'text-right' : ''}>
            <div className={`inline-block max-w-[85%] text-left px-3 py-2 rounded-lg text-xs leading-relaxed ${
              m.role === 'user'
                ? 'bg-trace-primary/20 text-trace-text'
                : m.isError
                  ? 'bg-trace-danger/10 border border-trace-danger/30 text-trace-danger'
                  : 'bg-trace-surface-2 text-trace-text'
            }`}>
              {m.text || (streaming && i === messages.length - 1 ? <span className="animate-pulse">…</span> : '')}
              {m.citations?.length > 0 && (
                <div className="mt-2 pt-2 border-t border-trace-border space-y-1">
                  <p className="text-[9px] uppercase tracking-wider text-trace-text-dim">Sources</p>
                  {m.citations.slice(0, 4).map((c) => (
                    <p key={c.provenance_id} className="text-[10px] text-trace-text-dim truncate">
                      📄 {c.filename} p.{c.page} ¶{c.paragraph} — "{c.snippet.slice(0, 60)}…"
                    </p>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
      <form onSubmit={submit} className="flex gap-2 p-3 border-t border-trace-border">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="How is X connected to Y?"
          className="input-field flex-1 text-xs"
        />
        <button type="submit" disabled={streaming || !input.trim()} className="btn-primary px-3">
          <Send className="w-3.5 h-3.5" />
        </button>
      </form>
    </div>
  );
}

function SimulateTab({ caseId, nodes, onHighlight, articulationPoints }) {
  const [target, setTarget] = useState('');
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);

  const run = async () => {
    if (!target) return;
    setRunning(true);
    try {
      const { data } = await api.post(`/api/cases/${caseId}/analysis/simulate-removal/${target}`);
      setResult(data);
      if (onHighlight && data.metrics) onHighlight(data.metrics.fragmented_away);
    } catch (err) {
      alert(err.response?.data?.detail || 'Simulation failed');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="p-3 space-y-3 text-xs overflow-y-auto h-full">
      <div className="flex items-center gap-2">
        <select value={target} onChange={(e) => setTarget(e.target.value)} className="input-field flex-1 text-xs">
          <option value="">Select entity to hypothetically remove…</option>
          {nodes.filter((n) => n.entity_type === 'PERSON' || n.entity_type === 'ORG').map((n) => (
            <option key={n.id} value={n.id}>
              {n.label}{articulationPoints.includes(n.id) ? ' ★ articulation point' : ''}
            </option>
          ))}
        </select>
        <button onClick={run} disabled={!target || running} className="btn-primary py-1.5 px-3 flex items-center gap-1">
          <Scissors className="w-3.5 h-3.5" /> Simulate
        </button>
      </div>

      {result && !result.metrics && (
        <p className="text-trace-text-dim">Entity is not part of the connected network.</p>
      )}

      {result?.metrics && (
        <div className="space-y-2">
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2 rounded bg-trace-surface-2 text-center">
              <p className="text-[9px] text-trace-text-dim uppercase">Groups before → after</p>
              <p className="text-trace-text font-semibold">
                {result.before.components} → {result.after.components}
                <span className={result.metrics.components_delta > 0 ? 'text-trace-accent' : 'text-trace-success'}>
                  {' '}{result.metrics.components_delta > 0 ? `+${result.metrics.components_delta}` : '±0'}
                </span>
              </p>
            </div>
            <div className="p-2 rounded bg-trace-surface-2 text-center">
              <p className="text-[9px] text-trace-text-dim uppercase">Largest group</p>
              <p className="text-trace-text font-semibold">
                {(result.before.largest_share * 100).toFixed(0)}% → {(result.after.largest_share * 100).toFixed(0)}%
              </p>
            </div>
            <div className="p-2 rounded bg-trace-surface-2 text-center">
              <p className="text-[9px] text-trace-text-dim uppercase">Cut off</p>
              <p className="text-trace-text font-semibold">{result.metrics.fragmented_count}</p>
            </div>
          </div>

          {result.metrics.fragmented_count > 0 && (
            <div className="p-2 rounded bg-trace-accent/10 border border-trace-accent/20 text-trace-accent flex items-center gap-2">
              <AlertTriangle className="w-3.5 h-3.5" />
              Highlighted on canvas: {result.metrics.fragmented_away.length} node(s) disconnected by this removal.
            </div>
          )}

          <ul className="list-disc pl-4 space-y-1 text-trace-text-muted">
            {result.explanation.map((b, i) => <li key={i}>{b}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

function PriorityTab({ caseId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/api/cases/${caseId}/priority-scores`)
      .then(({ data }) => setData(data))
      .catch(() => setData({ scores: [] }))
      .finally(() => setLoading(false));
  }, [caseId]);

  if (loading) return <div className="p-4 text-xs text-trace-text-dim">Computing…</div>;
  if (!data?.scores?.length) return <div className="p-4 text-xs text-trace-text-dim">No scores yet — sync the graph first.</div>;

  return (
    <div className="p-3 space-y-2 overflow-y-auto h-full text-xs">
      {data.scores.slice(0, 8).map((s) => (
        <details key={s.entity_id} className="p-2 rounded bg-trace-surface-2">
          <summary className="flex items-center justify-between cursor-pointer">
            <span className="text-trace-text">{s.name}</span>
            <span className="flex items-center gap-2">
              <span className="w-24 h-1.5 rounded bg-trace-surface-3 overflow-hidden">
                <span className="block h-full bg-trace-primary" style={{ width: `${s.score}%` }} />
              </span>
              <span className="font-mono text-trace-accent">{s.score.toFixed(0)}</span>
            </span>
          </summary>
          <ul className="list-disc pl-4 mt-2 space-y-1 text-trace-text-muted">
            {s.explanation.map((b, i) => <li key={i}>{b}</li>)}
          </ul>
        </details>
      ))}
    </div>
  );
}

export default function AnalysisPanel({ caseId, nodes, articulationPoints, onHighlightPath, onHighlightNodes, onClose }) {
  const [tab, setTab] = useState('chat');

  return (
    <div className="h-72 border-t border-trace-border bg-trace-surface flex flex-col animate-slide-in-up">
      <div className="flex items-center border-b border-trace-border px-2">
        {[
          { id: 'chat', label: 'Connections Chat', icon: MessageSquare },
          { id: 'sim', label: 'Disruption Simulator', icon: Scissors },
          { id: 'prio', label: 'Priority Score', icon: BarChart3 },
        ].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-1.5 px-3 py-2.5 text-xs border-b-2 transition-colors ${
              tab === id ? 'border-trace-primary text-trace-primary' : 'border-transparent text-trace-text-muted hover:text-trace-text'
            }`}
          >
            <Icon className="w-3.5 h-3.5" /> {label}
          </button>
        ))}
        <button onClick={onClose} className="ml-auto p-2 text-trace-text-dim hover:text-trace-text">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 min-h-0">
        {tab === 'chat' && <ChatTab caseId={caseId} onPath={onHighlightPath} />}
        {tab === 'sim' && (
          <SimulateTab caseId={caseId} nodes={nodes} onHighlight={onHighlightNodes} articulationPoints={articulationPoints} />
        )}
        {tab === 'prio' && <PriorityTab caseId={caseId} />}
      </div>
    </div>
  );
}
