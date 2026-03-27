import { Link } from 'react-router-dom'

export default function SiteHeader({ children }) {
  return (
    <header className="site-header">
      <Link to="/">CS2 <span>Demo Viewer</span></Link>
      {children}
    </header>
  )
}
