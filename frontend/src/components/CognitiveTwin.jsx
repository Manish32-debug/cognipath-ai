import {
  PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Tooltip,
} from 'recharts'
import { Card } from './Card.jsx'
import { riskClass } from '../utils/format.js'

/** Cognitive Digital Twin. Every trait is an INFERRED index, labelled as such,
 *  with the inputs it was derived from shown on hover/inline. */
export default function CognitiveTwin({ twin }) {
  if (!twin) return null
  const data = twin.traits.map((t) => ({ trait: t.trait, value: t.value }))

  return (
    <Card title="Cognitive Digital Twin"
      subtitle="Estimated learning profile derived from academic and behavioural indicators."
      right={twin.academic_risk && <span className={riskClass(twin.academic_risk)}>{twin.academic_risk} risk</span>}>

      <div className="grid grid-2" style={{ alignItems: 'center' }}>
        <ResponsiveContainer width="100%" height={260}>
          <RadarChart data={data} outerRadius={92}>
            <PolarGrid stroke="#253052" />
            <PolarAngleAxis dataKey="trait" tick={{ fill: '#9aa6c4', fontSize: 10.5 }} />
            <PolarRadiusAxis domain={[0, 100]} tick={{ fill: '#5a668a', fontSize: 9 }} />
            <Tooltip contentStyle={{ background: '#141c33', border: '1px solid #253052', borderRadius: 10, fontSize: 12 }} />
            <Radar dataKey="value" stroke="#22d3ee" fill="#6366f1" fillOpacity={0.35} />
          </RadarChart>
        </ResponsiveContainer>

        <div className="stack" style={{ gap: '.6rem' }}>
          {twin.traits.map((t) => (
            <div key={t.trait}>
              <div className="between small">
                <span>{t.trait} <span className="chip tiny">{t.status}</span></span>
                <span className="mono">{t.value} &middot; {t.band}</span>
              </div>
              <div className="tiny muted">{t.basis} (evidence: {t.evidence_strength})</div>
            </div>
          ))}
          <div className="small">
            <b>Learning style:</b> {twin.learning_style}
            <div className="tiny muted">{twin.learning_style_note}</div>
          </div>
        </div>
      </div>

      <div className="row wrap" style={{ marginTop: '.9rem', gap: '.5rem' }}>
        {twin.root_cause_concepts?.map((c) => <span key={c} className="badge badge-root">{c}</span>)}
        {twin.weak_concepts?.slice(0, 6).map((c) => <span key={c} className="chip">{c}</span>)}
      </div>

      <div className="notice notice-warn" style={{ marginTop: '.9rem' }}>{twin.disclaimer}</div>
    </Card>
  )
}
