import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { riskColor } from '../utils/format.js'

const axis = { stroke: '#9aa6c4', fontSize: 11 }
const tooltip = { background: '#141c33', border: '1px solid #253052', borderRadius: 10, fontSize: 12 }

export function RiskDistributionChart({ distribution = {}, height = 250 }) {
  const data = Object.entries(distribution).map(([name, value]) => ({ name, value }))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={3}>
          {data.map((d) => <Cell key={d.name} fill={riskColor(d.name)} />)}
        </Pie>
        <Tooltip contentStyle={tooltip} formatter={(v, n) => [`${v} students`, `${n} risk`]} />
        <Legend wrapperStyle={{ fontSize: 12, color: '#9aa6c4' }} />
      </PieChart>
    </ResponsiveContainer>
  )
}

export function ConceptWeaknessChart({ concepts = [], height = 320 }) {
  const data = concepts.slice(0, 10).map((c) => ({ name: c.label, mastery: c.average_mastery }))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ left: 10, right: 20 }}>
        <CartesianGrid stroke="#253052" strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" domain={[0, 100]} {...axis} />
        <YAxis type="category" dataKey="name" width={135} {...axis} />
        <Tooltip contentStyle={tooltip} formatter={(v) => [`${v}%`, 'Cohort average mastery']} />
        <Bar dataKey="mastery" barSize={14} radius={[3, 3, 3, 3]}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.mastery < 40 ? '#f87171' : d.mastery < 60 ? '#fbbf24' : '#34d399'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
