import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { ApiError } from '../api/client';
import {
  fetchKnowledgeGraph,
  type GraphEdge,
  type GraphNode,
  type GraphNodeType,
  type GraphResponse,
} from '../api/knowledge';
import AmbientLayer from '../appearance/AmbientLayer';
import { useAmbientEffect } from '../appearance/AppearanceProvider';
import { useI18n } from '../i18n';

const SIZE = 920;
const CX = SIZE / 2;
const CY = SIZE / 2;

type Point = { x: number; y: number };

function clamp(n: number, min: number, max: number) {
  return Math.min(max, Math.max(min, n));
}

function hashAngle(id: string): number {
  let h = 0;
  for (let i = 0; i < id.length; i += 1) h = (h * 33 + id.charCodeAt(i)) >>> 0;
  return (h % 1000) / 1000;
}

function placeRing(
  list: GraphNode[],
  radius: number,
  pos: Map<string, Point>,
  extra = 0,
) {
  const n = Math.max(list.length, 1);
  list.forEach((node, i) => {
    const jitter = (hashAngle(node.id) - 0.5) * 0.22;
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2 + extra + jitter;
    const r = radius + (hashAngle(node.id + 'r') - 0.5) * 22;
    pos.set(node.id, {
      x: CX + Math.cos(angle) * r,
      y: CY + Math.sin(angle) * r,
    });
  });
}

function layout(nodes: GraphNode[]): Map<string, Point> {
  const pos = new Map<string, Point>();
  const categories = nodes.filter((n) => n.type === 'category');
  const keywords = nodes
    .filter((n) => n.type === 'keyword')
    .sort((a, b) => b.weight - a.weight);
  const notes = nodes.filter((n) => n.type === 'knowledge');

  placeRing(categories, 92, pos);
  const split = Math.max(1, Math.ceil(keywords.length * 0.45));
  placeRing(keywords.slice(0, split), 178, pos, 0.18);
  placeRing(keywords.slice(split), 248, pos, -0.12);

  const byCat = new Map<string, GraphNode[]>();
  const uncategorized: GraphNode[] = [];
  for (const note of notes) {
    const cat = String(note.meta.category || '');
    if (!cat) {
      uncategorized.push(note);
      continue;
    }
    const bucket = byCat.get(cat) ?? [];
    bucket.push(note);
    byCat.set(cat, bucket);
  }

  for (const [cat, group] of byCat) {
    const origin = pos.get(`cat:${cat}`);
    const base = origin
      ? Math.atan2(origin.y - CY, origin.x - CX)
      : -Math.PI / 2;
    const spread = Math.min(1.15, (Math.PI * 0.7) / Math.max(group.length, 1));
    group.forEach((node, i) => {
      const angle = base + (i - (group.length - 1) / 2) * spread;
      const r = 318 + (hashAngle(node.id) - 0.5) * 16;
      pos.set(node.id, {
        x: CX + Math.cos(angle) * r,
        y: CY + Math.sin(angle) * r,
      });
    });
  }
  placeRing(uncategorized, 318, pos, 0.4);
  return pos;
}

function nodeFill(type: GraphNodeType): string {
  if (type === 'knowledge') return 'url(#km-fill-note)';
  if (type === 'keyword') return 'url(#km-fill-kw)';
  return 'url(#km-fill-cat)';
}

function nodeGlow(type: GraphNodeType): string {
  if (type === 'knowledge') return 'url(#km-glow-note)';
  if (type === 'keyword') return 'url(#km-glow-kw)';
  return 'url(#km-glow-cat)';
}

function nodeRadius(node: GraphNode, maxWeight: number): number {
  const t = node.weight / Math.max(maxWeight, 1);
  if (node.type === 'knowledge') return 7.5 + t * 3.5;
  if (node.type === 'keyword') return 3.2 + t * 4.2;
  return 10 + t * 5;
}

function edgeTone(type: GraphEdge['type']): string {
  if (type === 'in_category') return 'rgba(251, 191, 36, 0.42)';
  if (type === 'has_keyword') return 'rgba(45, 212, 191, 0.38)';
  return 'rgba(96, 165, 250, 0.22)';
}

function clipLabel(text: string, max = 10): string {
  const chars = [...text];
  if (chars.length <= max) return text;
  return `${chars.slice(0, max).join('')}…`;
}

function estimateWidth(text: string, fontSize: number): number {
  let w = 0;
  for (const ch of text) {
    w += /[\u4e00-\u9fff]/.test(ch) ? fontSize : fontSize * 0.58;
  }
  return w;
}

function buildAdjacency(edges: GraphEdge[]) {
  const adj = new Map<string, Set<string>>();
  for (const edge of edges) {
    if (!adj.has(edge.source)) adj.set(edge.source, new Set());
    if (!adj.has(edge.target)) adj.set(edge.target, new Set());
    adj.get(edge.source)!.add(edge.target);
    adj.get(edge.target)!.add(edge.source);
  }
  return adj;
}

export default function KnowledgeGraphPage() {
  const { t } = useI18n();
  const graphFx = useAmbientEffect('graph');
  const navigate = useNavigate();
  const stageRef = useRef<HTMLDivElement>(null);
  const drag = useRef<{
    x: number;
    y: number;
    ox: number;
    oy: number;
  } | null>(null);

  const [data, setData] = useState<GraphResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [hover, setHover] = useState<string | null>(null);
  const [cam, setCam] = useState({ x: 0, y: 0, k: 1 });

  useEffect(() => {
    fetchKnowledgeGraph()
      .then(setData)
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : t('km.graphFailed'));
      })
      .finally(() => setLoading(false));
  }, [t]);

  useEffect(() => {
    const el = stageRef.current;
    if (!el) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const factor = event.deltaY > 0 ? 0.9 : 1.1;
      setCam((prev) => ({ ...prev, k: clamp(prev.k * factor, 0.55, 2.5) }));
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, [data]);

  const positions = useMemo(
    () => (data ? layout(data.nodes) : new Map<string, Point>()),
    [data],
  );
  const adjacency = useMemo(
    () => (data ? buildAdjacency(data.edges) : new Map<string, Set<string>>()),
    [data],
  );
  const maxWeight = useMemo(() => {
    if (!data?.nodes.length) return 1;
    return Math.max(...data.nodes.map((n) => n.weight), 1);
  }, [data]);

  const related = useMemo(() => {
    if (!hover) return null;
    const set = new Set<string>([hover]);
    adjacency.get(hover)?.forEach((id) => set.add(id));
    return set;
  }, [hover, adjacency]);

  const hoverNode = hover
    ? data?.nodes.find((n) => n.id === hover)
    : undefined;

  function onNodeClick(node: GraphNode) {
    if (node.type !== 'knowledge') return;
    const raw = node.meta.knowledge_id;
    if (typeof raw === 'string' && raw) navigate(`/knowledge/${raw}`);
  }

  function onPointerDown(event: React.PointerEvent<HTMLDivElement>) {
    if ((event.target as HTMLElement).closest('[data-node]')) return;
    drag.current = {
      x: event.clientX,
      y: event.clientY,
      ox: cam.x,
      oy: cam.y,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function onPointerMove(event: React.PointerEvent<HTMLDivElement>) {
    if (!drag.current) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const scale = SIZE / Math.max(rect.width, 1);
    const nextX = drag.current.ox + (event.clientX - drag.current.x) * scale;
    const nextY = drag.current.oy + (event.clientY - drag.current.y) * scale;
    setCam((prev) => ({ ...prev, x: nextX, y: nextY }));
  }

  function onPointerUp() {
    drag.current = null;
  }

  const world = `translate(${CX + cam.x} ${CY + cam.y}) scale(${cam.k}) translate(${-CX} ${-CY})`;

  return (
    <div className="page page--graph">
      <header className="page__header">
        <div>
          <h1 className="page__title">{t('km.graphTitle')}</h1>
          <p className="page__subtitle">
            {data
              ? t('km.graphLead', {
                  notes: data.stats.knowledge,
                  keywords: data.stats.keyword,
                  edges: data.stats.edges,
                })
              : t('km.graphSubtitle')}
          </p>
        </div>
      </header>

      {error && <p className="banner banner--error">{error}</p>}
      {loading && <p className="faint">{t('common.loading')}</p>}

      {data && data.nodes.length === 0 && (
        <p className="empty">{t('km.graphEmpty')}</p>
      )}

      {data && data.nodes.length > 0 && (
        <div
          ref={stageRef}
          className={graphFx !== 'none' ? 'km-graph km-graph--ambient' : 'km-graph'}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          onDoubleClick={() => setCam({ x: 0, y: 0, k: 1 })}
        >
          <AmbientLayer surface="graph" />
          <svg
            viewBox={`0 0 ${SIZE} ${SIZE}`}
            preserveAspectRatio="xMidYMid meet"
            role="img"
            aria-label={t('km.graphTitle')}
          >
            <defs>
              <radialGradient id="km-fill-note">
                <stop offset="0%" stopColor="#99f6e4" />
                <stop offset="55%" stopColor="#2dd4bf" />
                <stop offset="100%" stopColor="#0f766e" />
              </radialGradient>
              <radialGradient id="km-fill-kw">
                <stop offset="0%" stopColor="#bfdbfe" />
                <stop offset="60%" stopColor="#60a5fa" />
                <stop offset="100%" stopColor="#1d4ed8" />
              </radialGradient>
              <radialGradient id="km-fill-cat">
                <stop offset="0%" stopColor="#fde68a" />
                <stop offset="55%" stopColor="#fbbf24" />
                <stop offset="100%" stopColor="#b45309" />
              </radialGradient>
              <filter id="km-glow-note" x="-90%" y="-90%" width="280%" height="280%">
                <feGaussianBlur stdDeviation="3.2" result="b" />
                <feMerge>
                  <feMergeNode in="b" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
              <filter id="km-glow-kw" x="-90%" y="-90%" width="280%" height="280%">
                <feGaussianBlur stdDeviation="2.4" result="b" />
                <feMerge>
                  <feMergeNode in="b" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
              <filter id="km-glow-cat" x="-90%" y="-90%" width="280%" height="280%">
                <feGaussianBlur stdDeviation="3.8" result="b" />
                <feMerge>
                  <feMergeNode in="b" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            <g transform={world}>
              {data.edges.map((edge) => {
                const a = positions.get(edge.source);
                const b = positions.get(edge.target);
                if (!a || !b) return null;
                const lit = related
                  ? related.has(edge.source) && related.has(edge.target)
                  : false;
                const idle = related ? 0.04 : edge.type === 'co_occur' ? 0.09 : 0.22;
                return (
                  <line
                    key={edge.id}
                    x1={a.x}
                    y1={a.y}
                    x2={b.x}
                    y2={b.y}
                    stroke={lit ? edgeTone(edge.type) : 'rgba(186, 214, 232, 0.16)'}
                    strokeWidth={lit ? 1.7 : edge.type === 'co_occur' ? 0.6 : 0.9}
                    opacity={lit ? 0.95 : idle}
                  />
                );
              })}

              {data.nodes.map((node) => {
                const p = positions.get(node.id);
                if (!p) return null;
                const r = nodeRadius(node, maxWeight);
                const active = !related || related.has(node.id);
                const showLabel =
                  node.type !== 'keyword' ||
                  hover === node.id ||
                  (!hover && node.weight >= maxWeight * 0.62);
                const label = clipLabel(
                  node.label,
                  node.type === 'keyword' ? 8 : 11,
                );
                const lw = estimateWidth(label, node.type === 'category' ? 11 : 10);
                return (
                  <g
                    key={node.id}
                    data-node={node.id}
                    transform={`translate(${p.x},${p.y})`}
                    opacity={active ? 1 : 0.16}
                    onMouseEnter={() => setHover(node.id)}
                    onMouseLeave={() => setHover(null)}
                    onClick={() => onNodeClick(node)}
                    style={{
                      cursor:
                        node.type === 'knowledge' ? 'pointer' : 'default',
                    }}
                  >
                    {node.type !== 'keyword' && (
                      <circle
                        className="km-graph__halo"
                        r={r + 7}
                        fill={
                          node.type === 'knowledge'
                            ? 'rgba(45, 212, 191, 0.16)'
                            : 'rgba(251, 191, 36, 0.16)'
                        }
                      />
                    )}
                    <circle
                      r={r}
                      fill={nodeFill(node.type)}
                      filter={nodeGlow(node.type)}
                      stroke="rgba(255,255,255,0.35)"
                      strokeWidth={hover === node.id ? 1.4 : 0.6}
                    />
                    {showLabel && (
                      <g>
                        <rect
                          x={-lw / 2 - 6}
                          y={r + 6}
                          width={lw + 12}
                          height={node.type === 'category' ? 18 : 16}
                          rx={8}
                          fill="rgba(5, 12, 20, 0.72)"
                          stroke="rgba(255,255,255,0.08)"
                        />
                        <text
                          y={r + (node.type === 'category' ? 19 : 17.5)}
                          textAnchor="middle"
                          fontSize={node.type === 'category' ? 11 : 10}
                          fill={
                            node.type === 'category' ? '#fde68a' : '#e8f4f2'
                          }
                          fontWeight={node.type === 'category' ? 700 : 500}
                        >
                          {label}
                        </text>
                      </g>
                    )}
                  </g>
                );
              })}
            </g>
          </svg>

          <div className="km-graph__hud">
            <p className="km-graph__hint">{t('km.graphHint')}</p>
            <div className="km-graph__legend">
              <span>
                <i className="km-graph__swatch km-graph__swatch--note" />
                {t('km.nodeNote')}
              </span>
              <span>
                <i className="km-graph__swatch km-graph__swatch--kw" />
                {t('km.nodeKeyword')}
              </span>
              <span>
                <i className="km-graph__swatch km-graph__swatch--cat" />
                {t('km.nodeCategory')}
              </span>
            </div>
          </div>

          {hoverNode && (
            <div className="km-graph__tip">
              <span className="km-graph__tip-kicker">
                {hoverNode.type === 'knowledge'
                  ? t('km.nodeNote')
                  : hoverNode.type === 'keyword'
                    ? t('km.nodeKeyword')
                    : t('km.nodeCategory')}
              </span>
              <strong>{hoverNode.label}</strong>
              {typeof hoverNode.meta.summary === 'string' &&
                hoverNode.meta.summary && (
                  <p>{hoverNode.meta.summary}</p>
                )}
              {hoverNode.type === 'knowledge' && (
                <em>{t('km.graphOpen')}</em>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
