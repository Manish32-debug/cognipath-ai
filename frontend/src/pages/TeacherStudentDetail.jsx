import { useNavigate, useParams } from 'react-router-dom'
import Navbar from '../components/Navbar.jsx'
import Sidebar from '../components/Sidebar.jsx'
import { Async } from '../components/Loader.jsx'
import { Card } from '../components/Card.jsx'
import PredictionCard from '../components/PredictionCard.jsx'
import RootCausePanel from '../components/RootCausePanel.jsx'
import RecommendationCard from '../components/RecommendationCard.jsx'
import StudyPlan from '../components/StudyPlan.jsx'
import CognitiveTwin from '../components/CognitiveTwin.jsx'
import ConceptMastery from '../components/ConceptMastery.jsx'
import SHAPChart from '../charts/SHAPChart.jsx'
import KnowledgeGraph from '../graph/KnowledgeGraph.jsx'
import { useApi } from '../hooks/useApi.js'
import { endpoints } from '../services/api.js'

const ITEMS = [{ to: '/teacher', label: 'Back to cohort', icon: '\u2190', end: true }]

/** Teacher drill-down: the same pipeline output a student sees, read-only. */
export default function TeacherStudentDetail() {
  const { studentId } = useParams()
  const navigate = useNavigate()
  const { data, error, loading, reload } = useApi(() => endpoints.teacherStudent(studentId), [studentId])
  const { data: graph } = useApi(() => endpoints.knowledgeGraph(), [])

  const masteryMap = data ? Object.fromEntries(data.mastery.concepts.map((c) => [c.concept, c.mastery])) : {}
  const labelled = data
    ? data.mastery.concepts.map((c) => ({
        ...c, label: graph?.nodes.find((n) => n.id === c.concept)?.label || c.concept,
      }))
    : []

  return (
    <div className="shell">
      <Sidebar items={ITEMS} />
      <div>
        <Navbar title={data?.student?.display_name || studentId}
          subtitle={`Student ID ${studentId}`} notice="teacher view" />
        <main className="content">
          <button className="btn btn-sm" style={{ marginBottom: '1rem' }} onClick={() => navigate('/teacher')}>
            &larr; Back to cohort
          </button>
          <Async loading={loading} error={error} onRetry={reload} height={140}
            label="Running the full pipeline for this student...">
            {data && (
              <div className="stack">
                <PredictionCard prediction={data.prediction} />

                <Card title="SHAP explanation"
                  subtitle={`${data.explanation.model} \u00B7 ${data.explanation.units}`}>
                  <SHAPChart contributions={data.explanation.top_contributions} units={data.explanation.units} />
                </Card>

                {graph && (
                  <Card title="Prerequisite graph" subtitle="Weak concepts in amber/red, likely root causes ringed in cyan.">
                    <KnowledgeGraph graph={graph} mastery={masteryMap} rootCauses={data.root_cause.root_causes} />
                  </Card>
                )}

                <ConceptMastery concepts={labelled} source={data.mastery.source} />
                <RootCausePanel analysis={data.root_cause} />
                <RecommendationCard recommendations={data.recommendations} />
                <StudyPlan plan={data.study_plan} />
                <CognitiveTwin twin={data.cognitive_twin} />
              </div>
            )}
          </Async>
        </main>
      </div>
    </div>
  )
}
