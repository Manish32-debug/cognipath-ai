import { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import ConceptMastery from '../../components/ConceptMastery.jsx'
import KnowledgeGraph from '../../graph/KnowledgeGraph.jsx'
import { Card } from '../../components/Card.jsx'
import { Async } from '../../components/Loader.jsx'
import { useApi } from '../../hooks/useApi.js'
import { endpoints } from '../../services/api.js'

export default function Mastery() {
  const { data, saveMastery } = useOutletContext()
  const [selected, setSelected] = useState(null)
  const { data: graph, error, loading, reload } = useApi(() => endpoints.knowledgeGraph(), [])

  const masteryMap = Object.fromEntries(data.mastery.concepts.map((c) => [c.concept, c.mastery]))
  const labelled = data.mastery.concepts.map((c) => ({
    ...c,
    label: graph?.nodes.find((n) => n.id === c.concept)?.label || c.concept,
  }))

  return (
    <div className="stack">
      <Card title="Prerequisite knowledge graph"
        subtitle="A directed acyclic graph in NetworkX. Arrows run from prerequisite to dependent concept.">
        <Async loading={loading} error={error} onRetry={reload} height={320}
          label="Tracing prerequisite dependencies...">
          {graph && (
            <KnowledgeGraph graph={graph} mastery={masteryMap}
              rootCauses={data.root_cause.root_causes} onSelect={setSelected} />
          )}
        </Async>
      </Card>

      {selected && (
        <Card title={selected.label} subtitle={`${selected.area} \u00B7 curriculum level ${selected.level}`}
          right={<span className="chip mono">{Math.round(masteryMap[selected.id] ?? 0)}% mastery</span>}>
          <p className="small">{selected.description}</p>
          <div className="grid grid-2">
            <div>
              <div className="tiny muted">Requires first</div>
              <div className="row wrap">
                {selected.prerequisites.length === 0 && <span className="tiny muted">nothing - this is a foundation concept</span>}
                {selected.prerequisites.map((p) => (
                  <span key={p} className="chip">{graph.nodes.find((n) => n.id === p)?.label}</span>
                ))}
              </div>
            </div>
            <div>
              <div className="tiny muted">Unlocks</div>
              <div className="row wrap">
                {selected.dependents.length === 0 && <span className="tiny muted">nothing further in this curriculum</span>}
                {selected.dependents.map((d) => (
                  <span key={d} className="chip">{graph.nodes.find((n) => n.id === d)?.label}</span>
                ))}
              </div>
            </div>
          </div>
        </Card>
      )}

      <ConceptMastery concepts={labelled} source={data.mastery.source} onSave={saveMastery} />
    </div>
  )
}
