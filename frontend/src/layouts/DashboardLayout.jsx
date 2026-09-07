import { Outlet } from 'react-router-dom'
import Navbar from '../components/Navbar.jsx'
import Sidebar from '../components/Sidebar.jsx'

export default function DashboardLayout({ items, title, subtitle, notice, footer, context }) {
  return (
    <div className="shell">
      <Sidebar items={items} footer={footer} />
      <div>
        <Navbar title={title} subtitle={subtitle} notice={notice} />
        <main className="content">
          <Outlet context={context} />
        </main>
      </div>
    </div>
  )
}
