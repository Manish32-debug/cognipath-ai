import { Navigate, Route, Routes } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute.jsx'
import Landing from './pages/Landing.jsx'
import Login from './pages/Login.jsx'
import NotFound from './pages/NotFound.jsx'
import StudentDashboard from './pages/StudentDashboard.jsx'
import TeacherDashboard from './pages/TeacherDashboard.jsx'
import TeacherStudentDetail from './pages/TeacherStudentDetail.jsx'
import Overview from './pages/student/Overview.jsx'
import Performance from './pages/student/Performance.jsx'
import Prediction from './pages/student/Prediction.jsx'
import Explainability from './pages/student/Explainability.jsx'
import Mastery from './pages/student/Mastery.jsx'
import RootCause from './pages/student/RootCause.jsx'
import Recommendations from './pages/student/Recommendations.jsx'
import Plan from './pages/student/Plan.jsx'
import Twin from './pages/student/Twin.jsx'
import Settings from './pages/student/Settings.jsx'
import Practice from './pages/student/Practice.jsx'
import Resources from './pages/student/Resources.jsx'
import SamplePapers from './pages/student/SamplePapers.jsx'
import PracticeHistory from './pages/student/PracticeHistory.jsx'
import Cohort from './pages/teacher/Cohort.jsx'
import Questions from './pages/teacher/Questions.jsx'
import TeacherResources from './pages/teacher/Resources.jsx'
import TeacherSamplePapers from './pages/teacher/SamplePapers.jsx'
import PracticeAnalytics from './pages/teacher/PracticeAnalytics.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />

      <Route path="/app" element={<ProtectedRoute><StudentDashboard /></ProtectedRoute>}>
        <Route index element={<Overview />} />
        <Route path="performance" element={<Performance />} />
        <Route path="prediction" element={<Prediction />} />
        <Route path="explainability" element={<Explainability />} />
        <Route path="mastery" element={<Mastery />} />
        <Route path="root-cause" element={<RootCause />} />
        <Route path="recommendations" element={<Recommendations />} />
        <Route path="study-plan" element={<Plan />} />
        <Route path="practice" element={<Practice />} />
        <Route path="practice-history" element={<PracticeHistory />} />
        <Route path="resources" element={<Resources />} />
        <Route path="sample-papers" element={<SamplePapers />} />
        <Route path="twin" element={<Twin />} />
        <Route path="settings" element={<Settings />} />
      </Route>

      <Route path="/teacher" element={<ProtectedRoute role="teacher"><TeacherDashboard /></ProtectedRoute>}>
        <Route index element={<Cohort />} />
        <Route path="questions" element={<Questions />} />
        <Route path="resources" element={<TeacherResources />} />
        <Route path="sample-papers" element={<TeacherSamplePapers />} />
        <Route path="practice-analytics" element={<PracticeAnalytics />} />
      </Route>

      <Route path="/teacher/student/:studentId"
        element={<ProtectedRoute role="teacher"><TeacherStudentDetail /></ProtectedRoute>} />

      <Route path="/dashboard" element={<Navigate to="/app" replace />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}
