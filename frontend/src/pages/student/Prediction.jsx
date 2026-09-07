import { useOutletContext } from 'react-router-dom'
import PredictionCard from '../../components/PredictionCard.jsx'
import { Card } from '../../components/Card.jsx'
import { useApi } from '../../hooks/useApi.js'
import { endpoints } from '../../services/api.js'
import { Async } from '../../components/Loader.jsx'
import { num } from '../../utils/format.js'

export default function Prediction() {
  const { data } = useOutletContext()
  const { data: evaluation, error, loading, reload } = useApi(() => endpoints.evaluation(), [])

  return (
    <div className="stack">
      <PredictionCard prediction={data.prediction} />

      <Card title="How these models were selected"
        subtitle="Candidates were compared by cross-validation on the training split only; the test split was scored once.">
        <Async loading={loading} error={error} onRetry={reload} label="Loading evaluation report...">
          {evaluation && (
            <div className="stack">
              {Object.entries(evaluation.tasks).map(([task, info]) => (
                <div key={task}>
                  <div className="between">
                    <strong className="small">{info.target}</strong>
                    <span className="chip">selected: {info.selected_model}</span>
                  </div>
                  <div className="tiny muted" style={{ margin: '.3rem 0 .5rem' }}>{info.selection_metric}</div>
                  <table>
                    <thead><tr><th>Candidate</th><th>Cross-validated score</th></tr></thead>
                    <tbody>
                      {Object.entries(info.candidates).map(([name, metrics]) => {
                        const [k, v] = Object.entries(metrics)[0]
                        return (
                          <tr key={name} style={name === info.selected_model ? { color: 'var(--brand-2)' } : undefined}>
                            <td>{name}</td>
                            <td className="mono">{k.replace(/_/g, ' ')}: {num(v, 4)}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          )}
        </Async>
      </Card>
    </div>
  )
}
