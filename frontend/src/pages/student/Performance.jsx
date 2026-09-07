import { useOutletContext } from 'react-router-dom'
import { Card, StatCard, Bar } from '../../components/Card.jsx'
import { GradeTrendChart, HistoryChart } from '../../charts/PerformanceChart.jsx'
import { STUDY_TIME_LABEL, num } from '../../utils/format.js'

export default function Performance() {
  const { data } = useOutletContext()
  const f = data.student.features

  return (
    <div className="stack">
      <div className="grid grid-4">
        <StatCard label="Period 1 (G1)" value={num(f.G1, 0)} suffix="/ 20" />
        <StatCard label="Period 2 (G2)" value={num(f.G2, 0)} suffix="/ 20" />
        <StatCard label="Attendance" value={num(f.attendance_pct, 0)} suffix="%"
          hint={`${num(f.absences, 0)} absences recorded`} />
        <StatCard label="Study time" value={f.studytime} suffix="/ 4"
          hint={STUDY_TIME_LABEL[f.studytime]} />
      </div>

      <div className="grid grid-2">
        <Card title="Grade trend" subtitle="Assessed periods and the predicted final period, on the 0-10 GPA scale.">
          <GradeTrendChart features={f} predictedGpa={data.prediction.predicted_gpa} />
        </Card>
        <Card title="Prediction history" subtitle="Every dashboard load logs the model output, so changes to your inputs are visible over time.">
          <HistoryChart history={data.history || []} />
        </Card>
      </div>

      <Card title="Behavioural indicators" subtitle="Raw inputs the model actually receives.">
        <div className="grid grid-2" style={{ gap: '1rem 2rem' }}>
          {[
            ['Attendance', f.attendance_pct, 100],
            ['Study time', f.studytime, 4],
            ['Free time', f.freetime, 5],
            ['Going out', f.goout, 5],
            ['Health status', f.health, 5],
            ['Family relationship', f.famrel, 5],
          ].map(([label, value, max]) => (
            <div key={label}>
              <div className="between small" style={{ marginBottom: '.25rem' }}>
                <span>{label}</span><span className="mono">{num(value, 1)} / {max}</span>
              </div>
              <Bar value={(Number(value) / max) * 100} />
            </div>
          ))}
        </div>
        <div className="notice" style={{ marginTop: '1rem' }}>
          Past course failures: <b>{num(f.failures, 0)}</b>. This is one of the strongest negative
          predictors in the dataset and appears explicitly in the SHAP explanation.
        </div>
      </Card>
    </div>
  )
}
