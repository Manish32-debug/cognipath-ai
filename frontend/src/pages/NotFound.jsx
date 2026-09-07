import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="container center" style={{ paddingTop: '18vh' }}>
      <h1 className="gradient-text">404</h1>
      <p>That page does not exist.</p>
      <Link className="btn btn-primary" to="/">Back to home</Link>
    </div>
  )
}
