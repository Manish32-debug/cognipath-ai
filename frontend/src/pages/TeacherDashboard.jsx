import { Outlet } from 'react-router-dom'
import Navbar from '../components/Navbar.jsx'
import Sidebar from '../components/Sidebar.jsx'

/** Shell for the teacher experience.
 *
 *  Converted from a single page into a nested-route layout so resource
 *  management, the question bank and practice analytics can live alongside the
 *  cohort overview. The cohort view itself is unchanged - it moved verbatim to
 *  `pages/teacher/Cohort.jsx` and is now the index route. */
const ITEMS = [
  { to: '/teacher', label: 'Cohort overview', icon: '\u25A6', end: true },
  { to: '/teacher/subject-analytics', label: 'Subject analytics', icon: '\u2637' },
  { to: '/teacher/assessments', label: 'Assessments', icon: '\u25A5' },
  { to: '/teacher/questions', label: 'Question bank', icon: '\u2261' },
  { to: '/teacher/resources', label: 'Study materials', icon: '\u2726' },
  { to: '/teacher/sample-papers', label: 'Sample papers', icon: '\u2637' },
  { to: '/teacher/practice-analytics', label: 'Practice analytics', icon: '\u2197' },
]

export default function TeacherDashboard() {
  return (
    <div className="shell">
      <Sidebar items={ITEMS}
        footer="Cohort analytics are computed by running the trained models over every stored student. Practice analytics aggregate stored attempts." />
      <div>
        <Navbar title="Teacher dashboard" subtitle="Cohort monitoring, content management and intervention triage" />
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
