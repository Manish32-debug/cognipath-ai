import { useMemo, useState } from 'react'

/** Interactive prerequisite graph.
 *
 *  Rendered as hand-drawn SVG rather than a force-directed library: the graph is
 *  a small DAG whose meaning IS its layering (prerequisites on the left, dependents
 *  on the right). A physics simulation would scramble that ordering and add a
 *  dependency for no gain. Node x-position comes from the backend's topological
 *  level; y-position spreads nodes within their level.
 *
 *  Colour = mastery band. Cyan ring = concept flagged as a likely root cause.
 *  Selecting a node highlights it, its prerequisites and its dependents.
 */
const COL_W = 190
const ROW_H = 82
const PAD = 46
const R = 26

function colorFor(mastery) {
  if (mastery == null) return '#39456f'
  if (mastery < 40) return '#f87171'
  if (mastery < 60) return '#fbbf24'
  if (mastery < 70) return '#a3a3f5'
  return '#34d399'
}

export default function KnowledgeGraph({ graph, mastery = {}, rootCauses = [], onSelect }) {
  const [selected, setSelected] = useState(null)
  const rootIds = useMemo(() => new Set(rootCauses.map((r) => r.concept)), [rootCauses])

  const layout = useMemo(() => {
    if (!graph) return null
    const byLevel = new Map()
    graph.nodes.forEach((n) => {
      if (!byLevel.has(n.level)) byLevel.set(n.level, [])
      byLevel.get(n.level).push(n)
    })
    const maxRows = Math.max(...[...byLevel.values()].map((v) => v.length))
    const positions = {}
    ;[...byLevel.entries()].forEach(([level, nodes]) => {
      nodes.forEach((n, i) => {
        const offset = (maxRows - nodes.length) / 2
        positions[n.id] = {
          x: PAD + level * COL_W,
          y: PAD + (i + offset) * ROW_H,
        }
      })
    })
    return {
      positions,
      width: PAD * 2 + (Math.max(...graph.nodes.map((n) => n.level))) * COL_W + 60,
      height: PAD * 2 + maxRows * ROW_H,
    }
  }, [graph])

  if (!graph || !layout) return null

  const related = new Set()
  if (selected) {
    related.add(selected)
    graph.edges.forEach((e) => {
      if (e.target === selected) related.add(e.source)
      if (e.source === selected) related.add(e.target)
    })
  }

  const pick = (id) => {
    const next = id === selected ? null : id
    setSelected(next)
    onSelect?.(next ? graph.nodes.find((n) => n.id === next) : null)
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <svg width={layout.width} height={layout.height} role="img"
        aria-label="Prerequisite knowledge graph" style={{ minWidth: '100%' }}>
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#3b4a7d" />
          </marker>
        </defs>

        {graph.edges.map((e, i) => {
          const a = layout.positions[e.source]
          const b = layout.positions[e.target]
          if (!a || !b) return null
          const dim = selected && !(related.has(e.source) && related.has(e.target))
          const mx = (a.x + b.x) / 2
          return (
            <path key={i}
              d={`M ${a.x + R} ${a.y} C ${mx} ${a.y}, ${mx} ${b.y}, ${b.x - R - 6} ${b.y}`}
              fill="none"
              stroke={dim ? '#1c2547' : '#3b4a7d'}
              strokeWidth={0.8 + e.strength * 1.6}
              markerEnd="url(#arrow)"
              opacity={dim ? 0.35 : 1} />
          )
        })}

        {graph.nodes.map((n) => {
          const p = layout.positions[n.id]
          const m = mastery[n.id]
          const dim = selected && !related.has(n.id)
          const isRoot = rootIds.has(n.id)
          return (
            <g key={n.id} transform={`translate(${p.x}, ${p.y})`}
              onClick={() => pick(n.id)} style={{ cursor: 'pointer' }} opacity={dim ? 0.3 : 1}>
              {isRoot && <circle r={R + 6} fill="none" stroke="#22d3ee" strokeWidth="2" strokeDasharray="4 3" />}
              <circle r={R} fill={colorFor(m)} fillOpacity={0.18}
                stroke={colorFor(m)} strokeWidth={n.id === selected ? 3 : 1.6} />
              <text textAnchor="middle" dy="4" fontSize="11" fontWeight="700" fill="#e8ecf8">
                {m == null ? '-' : `${Math.round(m)}%`}
              </text>
              <text textAnchor="middle" y={R + 15} fontSize="10.5" fill="#9aa6c4">
                {n.label.length > 20 ? `${n.label.slice(0, 19)}...` : n.label}
              </text>
            </g>
          )
        })}
      </svg>

      <div className="row wrap small muted" style={{ marginTop: '.6rem', gap: '1rem' }}>
        <span><b style={{ color: '#f87171' }}>&#9679;</b> below 40%</span>
        <span><b style={{ color: '#fbbf24' }}>&#9679;</b> 40-59%</span>
        <span><b style={{ color: '#a3a3f5' }}>&#9679;</b> 60-69%</span>
        <span><b style={{ color: '#34d399' }}>&#9679;</b> 70%+ (target met)</span>
        <span><b style={{ color: '#22d3ee' }}>&#9711;</b> likely root cause</span>
        <span>Arrows point from prerequisite to dependent. Click a node to isolate it.</span>
      </div>
    </div>
  )
}
