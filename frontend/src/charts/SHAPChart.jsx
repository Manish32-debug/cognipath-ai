import {
  Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

/** Horizontal SHAP contribution chart.
 *  Green bars push the prediction up, red bars push it down. Values come
 *  straight from the backend's SHAP explainer - nothing is computed here. */
export default function SHAPChart({ contributions = [], units = '', height = 340 }) {
  const data = contributions
    .slice()
    .sort((a, b) => a.shap_value - b.shap_value)
    .map((c) => ({ ...c, name: c.label }))

  if (!data.length) return <p className="small">No contributions returned for this prediction.</p>

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
        <XAxis type="number" stroke="#9aa6c4" fontSize={11}
          label={{ value: units, position: 'insideBottom', offset: -2, fill: '#9aa6c4', fontSize: 11 }} />
        <YAxis type="category" dataKey="name" width={165} stroke="#9aa6c4" fontSize={11} />
        <ReferenceLine x={0} stroke="#3b4a7d" />
        <Tooltip
          cursor={{ fill: 'rgba(99,102,241,.08)' }}
          contentStyle={{ background: '#141c33', border: '1px solid #253052', borderRadius: 10, fontSize: 12 }}
          formatter={(v, _n, p) => [`${v > 0 ? '+' : ''}${v}`, `Student value: ${p.payload.student_value ?? 'n/a'}`]}
        />
        <Bar dataKey="shap_value" radius={[3, 3, 3, 3]} barSize={14}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.shap_value >= 0 ? '#34d399' : '#f87171'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
