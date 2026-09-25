import { Link, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth/AuthProvider'
import { ErrorPanel, Loading } from './components/QueryState'
import { LoginPage, SignupPage } from './pages/Auth'
import { AssignedPage } from './pages/Assigned'
import { DashboardPage } from './pages/Dashboard'
import { ProjectsPage } from './pages/Projects'
import { Shell } from './pages/Shell'
import { BacklogTab } from './pages/project/Backlog'
import { BoardTab } from './pages/project/Board'
import { MembersTab } from './pages/project/Members'
import { ProjectPage } from './pages/project/ProjectPage'
import { ApiError } from './api/client'

function RequireAuth() {
  const { status, retry } = useAuth()
  const location = useLocation()

  if (status === 'loading') {
    return (
      <div className="fullscreen">
        <Loading label="TaskFlow" />
      </div>
    )
  }
  if (status === 'unreachable') {
    return (
      <div className="fullscreen">
        <ErrorPanel error={new ApiError(0, 'network', 'Could not reach the server. Check your connection and try again.')} onRetry={retry} />
      </div>
    )
  }
  if (status === 'anon') {
    return <Navigate to="/login" replace state={{ from: `${location.pathname}${location.search}` }} />
  }
  return <Outlet />
}

function NotFound() {
  return (
    <div className="page">
      <div className="state">
        <p>There is nothing at this address.</p>
        <Link className="btn" to="/">
          Back to projects
        </Link>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<Shell />}>
          <Route index element={<ProjectsPage />} />
          <Route path="assigned" element={<AssignedPage />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="projects/:projectId" element={<ProjectPage />}>
            <Route index element={<Navigate to="board" replace />} />
            <Route path="board" element={<BoardTab />} />
            <Route path="backlog" element={<BacklogTab />} />
            <Route path="members" element={<MembersTab />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Route>
      </Route>
    </Routes>
  )
}
