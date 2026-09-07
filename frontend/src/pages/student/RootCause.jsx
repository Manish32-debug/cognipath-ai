import { useOutletContext } from 'react-router-dom'
import RootCausePanel from '../../components/RootCausePanel.jsx'
import { Card } from '../../components/Card.jsx'

export default function RootCause() {
  const { data } = useOutletContext()
  const p = data.root_cause.parameters

  return (
    <div className="stack">
      <RootCausePanel analysis={data.root_cause} />

      <Card title="How the algorithm works" subtitle="Four steps, all executed over the real graph.">
        <ol className="small" style={{ paddingLeft: '1.1rem', lineHeight: 1.8 }}>
          <li><b>Gap.</b> gap(c) = max(0, {p.mastery_target} &minus; mastery) / {p.mastery_target}. A concept at or above target has zero gap and can never be blamed.</li>
          <li><b>Downstream pressure.</b> For every weak descendant d, add gap(d) &times; edge strength along the path &times; {p.decay}<sup>hops&minus;1</sup>. Weakness that shows up in many dependent concepts raises the suspicion on the prerequisite.</li>
          <li><b>Upstream clearance.</b> 1 &minus; (worst gap among this concept&apos;s own prerequisites), floored at {p.min_clearance}. If its own prerequisites are weak, the blame belongs further upstream.</li>
          <li><b>Score.</b> gap &times; (1 + {p.beta} &times; downstream pressure) &times; clearance, then rank.</li>
        </ol>
        <div className="notice notice-warn">
          Thresholds: weak below {p.weak_threshold}%, critical below {p.critical_threshold}%, adequate at {p.mastery_target}%.
          These are curriculum policy choices, not learned parameters.
        </div>
      </Card>
    </div>
  )
}
