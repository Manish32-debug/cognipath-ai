import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { Spinner } from './Loader.jsx'

/** Client-side guard. The real enforcement is server side (FastAPI checks the
 *  JWT role on every protected route); this only avoids rendering a page the
 *  API would refuse anyway. */
export default function ProtectedRoute({ role, children }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) return <div style={{ padding: '3rem' }}><Spinner label="Restoring session..." /></div>
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  if (role && user.role !== role) {
    return <Navigate to={user.role === 'teacher' ? '/teacher' : '/app'} replace />
  }
  return children
}
