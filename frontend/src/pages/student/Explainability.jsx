import { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { Card } from '../../components/Card.jsx'
import { Async } from '../../components/Loader.jsx'
import SHAPChart from '../../charts/SHAPChart.jsx'
import { useApi } from '../../hooks/useApi.js'
import { endpoints } from '../../services/api.js'

const TASKS = [
  ['gpa', 'Why this GPA?'],
  ['pass', 'Why this pass probability?'],
  ['risk', 'Why this risk tier?'],
]

export default function Explainability() {
  const { data } = useOutletContext()
  const [task, setTask] = useState('gpa')
  const features = data.student.features

  // The overview already has the GPA explanation; other tasks are fetched on demand.
  const { data: fetched, error, loading, reload } = useApi(
    () => endpoints.explain(features, task), [task],
  )
  const exp = task === 'gpa' && !fetched ? data.explanation : fetched

  return (
    <div className="stack">
      <Card title="SHAP explanation"
        subtitle="Each bar is how far that feature moved this student's prediction away from the dataset average."
        right={
          <div className="row">
            {TASKS.map(([id, label]) => (
              <button key={id} className={`btn btn-sm ${task === id ? 'btn-primary' : ''}`}
                onClick={() => setTask(id)}>{label}</button>
            ))}
          </div>
        }>
        <Async loading={loading && !exp} error={error} onRetry={reload} height={280}
          label="Calculating explanation...">
          {exp && (
            <>
              <div className="row wrap tiny muted" style={{ marginBottom: '.7rem', gap: '1rem' }}>
                <span>model <b>{exp.model}</b></span>
                <span>explainer <b>{exp.explainer}</b></span>
                <span>units <b>{exp.units}</b></span>
                <span>average baseline <b className="mono">{exp.base_value}</b></span>
                <span>this student <b className="mono">{exp.prediction}</b></span>
                {exp.explained_class && <span>explaining class <b>{exp.explained_class}</b></span>}
              </div>
              <SHAPChart contributions={exp.top_contributions} units={exp.units} />
            </>
          )}
        </Async>
      </Card>

      {exp && (
        <div className="grid grid-2">
          <Card title="What is helping" subtitle="Features pushing the prediction up.">
            <div className="stack" style={{ gap: '.45rem' }}>
              {exp.helping.length === 0 && <p className="small">Nothing is pushing this prediction upward.</p>}
              {exp.helping.map((c) => (
                <div key={c.feature} className="between small">
                  <span>{c.label} <span className="tiny muted">({c.student_value ?? 'n/a'})</span></span>
                  <span className="mono" style={{ color: 'var(--good)' }}>+{c.shap_value}</span>
                </div>
              ))}
            </div>
          </Card>
          <Card title="What is hurting" subtitle="Features pushing the prediction down.">
            <div className="stack" style={{ gap: '.45rem' }}>
              {exp.hurting.length === 0 && <p className="small">Nothing is pushing this prediction downward.</p>}
              {exp.hurting.map((c) => (
                <div key={c.feature} className="between small">
                  <span>{c.label} <span className="tiny muted">({c.student_value ?? 'n/a'})</span></span>
                  <span className="mono" style={{ color: 'var(--bad)' }}>{c.shap_value}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {exp && <div className="notice">{exp.explanation_note}</div>}
    </div>
  )
}
