import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

const axis = { stroke: '#9aa6c4', fontSize: 11 }
const tooltip = { background: '#141c33', border: '1px solid #253052', borderRadius: 10, fontSize: 12 }

/** Grade progression: the two real assessed periods (G1, G2) followed by the
 *  model's prediction for the final period, expressed on the 0-10 GPA scale. */
export function GradeTrendChart({ features, predictedGpa, height = 240 }) {
  const data = [
    { period: 'Period 1 (G1)', gpa: Number(features.G1) / 2, actual: true },
    { period: 'Period 2 (G2)', gpa: Number(features.G2) / 2, actual: true },
    { period: 'Final (predicted)', gpa: predictedGpa, actual: false },
  ]
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ left: -18, right: 12, top: 8 }}>
        <CartesianGrid stroke="#253052" strokeDasharray="3 3" />
        <XAxis dataKey="period" {...axis} />
        <YAxis domain={[0, 10]} {...axis} />
        <Tooltip contentStyle={tooltip} formatter={(v) => [`${Number(v).toFixed(2)} / 10`, 'GPA']} />
        <Line type="monotone" dataKey="gpa" stroke="#6366f1" strokeWidth={2.4}
          dot={{ r: 4, fill: '#22d3ee' }} activeDot={{ r: 6 }} />
      </LineChart>
    </ResponsiveContainer>
  )
}

/** Prediction history from the database - each dashboard load logs a prediction,
 *  so this shows how the estimate moves as the student's inputs are updated. */
export function HistoryChart({ history = [], height = 240 }) {
  if (history.length < 2) {
    return <p className="small">Not enough history yet. Predictions are logged each time this dashboard is opened; update your data to see the trend.</p>
  }
  const data = history.map((h, i) => ({
    run: `#${i + 1}`,
    gpa: h.predicted_gpa,
    pass: Math.round(h.pass_probability * 100) / 10,
  }))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ left: -18, right: 12, top: 8 }}>
        <CartesianGrid stroke="#253052" strokeDasharray="3 3" />
        <XAxis dataKey="run" {...axis} />
        <YAxis domain={[0, 10]} {...axis} />
        <Tooltip contentStyle={tooltip} />
        <Line type="monotone" dataKey="gpa" name="Predicted GPA" stroke="#6366f1" strokeWidth={2.2} dot={{ r: 3 }} />
        <Line type="monotone" dataKey="pass" name="Pass probability (x10)" stroke="#22d3ee" strokeWidth={2} strokeDasharray="4 3" dot={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}
