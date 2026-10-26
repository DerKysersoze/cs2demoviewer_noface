import { Link } from 'react-router-dom'
import useTheme from '../hooks/useTheme'

/** Crosshair logo, drawn in SVG (monochrome). */
function Logo() {
  return (
    <Link to="/" className="site-brand" aria-label="CS2 Demo Viewer home">
      <svg width="24" height="24" viewBox="0 0 32 32" aria-hidden="true">
        <circle cx="16" cy="16" r="10" fill="none" stroke="currentColor" strokeWidth="2" />
        <path d="M16 2v8M16 22v8M2 16h8M22 16h8" stroke="currentColor" strokeWidth="2" />
        <circle cx="16" cy="16" r="2" fill="currentColor" />
      </svg>
      <span className="site-brand-text">
        CS2 <span className="accent">Demo Viewer</span>
      </span>
    </Link>
  )
}

/** Sun/moon theme toggle, styled to sit with the header actions. */
function ThemeToggle() {
  const { theme, toggle } = useTheme()
  const dark = theme === 'dark'
  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={dark}
      aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
      title={dark ? 'Switch to light theme' : 'Switch to dark theme'}
      className="theme-toggle"
    >
      {dark ? (
        // sun
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="2" />
          <path
            d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1"
            stroke="currentColor"
            strokeWidth="2"
          />
        </svg>
      ) : (
        // moon
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinejoin="round"
          />
        </svg>
      )}
      {dark ? 'Light' : 'Dark'}
    </button>
  )
}

export default function SiteHeader({ children }) {
  return (
    <header className="site-header">
      <Logo />
      {children && <div className="site-header-actions">{children}</div>}
      <ThemeToggle />
    </header>
  )
}
