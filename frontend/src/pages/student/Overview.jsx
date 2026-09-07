import { useOutletContext } from 'react-router-dom'
import { StatCard, Card } from '../../components/Card.jsx'
import { GradeTrendChart } from '../../charts/PerformanceChart.jsx'
import SHAPChart from '../../charts/SHAPChart.jsx'
import { num, pct, riskColor } from '../../utils/format.js'

export default function Overview() {
  const { data } = useOutletContext()
  const { prediction, explanation, mastery, root_cause: rc, student } = data
  const topRoot = rc.root_causes?.[0]

  return (
    <div className="stack">
      <div className="grid grid-4">
        <StatCard label="Predicted GPA" value={num(prediction.predicted_gpa)} suffix="/ 10"
          hint={`Model: ${prediction.models_used.gpa}`} />
        <StatCard label="Pass probability" value={pct(prediction.pass_probability, 0)}
          hint="Final grade >= 10 / 20" />
        <StatCard label="Academic risk" value={prediction.risk_tier} tone={riskColor(prediction.risk_tier)}
          hint={`Model: ${prediction.models_used.risk}`} />
        <StatCard label="Overall mastery" value={mastery.overall ?? '-'} suffix="%"
          hint={`Source: ${mastery.source}`} />
      </div>

      <div className="grid grid-2">
        <Card title="Grade progression" subtitle="Two real assessed periods plus the model's estimate of the final period.">
          <GradeTrendChart features={student.features} predictedGpa={prediction.predicted_gpa} />
        </Card>
        <Card title="Top prediction drivers" subtitle={`SHAP on the ${explanation.model} model (${explanation.units}).`}>
          <SHAPChart contributions={explanation.top_contributions.slice(0, 7)} units={explanation.units} height={250} />
        </Card>
      </div>

      {topRoot && (
        <Card title="Most likely prerequisite gap" right={<span className="badge badge-root">{topRoot.label}</span>}>
          <p className="small" style={{ margin: 0 }}>{topRoot.reasoning}</p>
        </Card>
      )}
    </div>
  )
}
