import { Outlet } from 'react-router-dom'
import Navbar from '../components/Navbar.jsx'
import Sidebar from '../components/Sidebar.jsx'
import { Async } from '../components/Loader.jsx'
import { useApi } from '../hooks/useApi.js'
import { useAuth } from '../context/AuthContext.jsx'
import { endpoints } from '../services/api.js'

const ITEMS = [
  { to: '/app', label: 'Overview', icon: '\u25A6', end: true },
  { to: '/app/academics', label: 'Academic overview', icon: '\u2637' },
  { to: '/app/performance', label: 'Performance', icon: '\u2197' },
  { to: '/app/prediction', label: 'AI prediction', icon: '\u25C9' },
  { to: '/app/explainability', label: 'Explainability', icon: '\u2696' },
  { to: '/app/mastery', label: 'Concept mastery', icon: '\u25A4' },
  { to: '/app/root-cause', label: 'Root cause', icon: '\u2442' },
  { to: '/app/recommendations', label: 'Recommendations', icon: '\u2726' },
  { to: '/app/study-plan', label: 'Study plan', icon: '\u2637' },
  { to: '/app/practice', label: 'Practice', icon: '\u270E' },
  { to: '/app/practice-history', label: 'Practice history', icon: '\u23F1' },
  { to: '/app/resources', label: 'Study materials', icon: '\u2726' },
  { to: '/app/sample-papers', label: 'Sample papers', icon: '\u25A5' },
  { to: '/app/twin', label: 'Cognitive twin', icon: '\u25D1' },
  { to: '/app/settings', label: 'Settings', icon: '\u2699' },
]

/** Shell for the student experience. The whole pipeline is fetched once here
 *  (one API call runs prediction, SHAP, graph reasoning, recommendations, plan
 *  and twin) and shared with every section through the router outlet context. */
export default function StudentDashboard() {
  const { user } = useAuth()
  const studentId = user?.student_id
  const { data, error, loading, reload } = useApi(
    () => endpoints.dashboard(studentId), [studentId], { enabled: Boolean(studentId) },
  )

  const saveMastery = async (records) => {
    await endpoints.updateMastery(studentId, records)
    reload()
  }

  return (
    <div className="shell">
      <Sidebar items={ITEMS} footer={`Signed in as ${user?.username} \u00B7 ${studentId || 'no student record'}`} />
      <div>
        <Navbar
          title={data?.student?.display_name || 'Student dashboard'}
          subtitle={studentId ? `Student ID ${studentId}` : undefined}
          notice={data?.student?.is_demo ? 'demo record' : undefined} />
        <main className="content">
          {!studentId && (
            <div className="notice notice-warn">
              This account has no linked student record. Ask a teacher to create one, or sign in with a demo student account.
            </div>
          )}
          <Async loading={loading} error={error} onRetry={reload} height={140}
            label="Running prediction, SHAP explanation, graph traversal and recommendations...">
            {data && <Outlet context={{ data, reload, saveMastery, studentId }} />}
          </Async>
        </main>
      </div>
    </div>
  )
}
