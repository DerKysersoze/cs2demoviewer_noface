import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'cs2-theme'

function systemPrefersDark() {
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

/**
 * useTheme — light/dark theme with system fallback + persistence.
 *
 * - Explicit choice (from the header toggle) is stored in localStorage
 *   and always wins.
 * - Without an explicit choice, follows the OS `prefers-color-scheme`
 *   and live-updates when it changes.
 * - The `dark` class is applied to <html>; index.html sets it before
 *   first paint to avoid a flash of the wrong theme.
 */
export default function useTheme() {
  const [theme, setTheme] = useState(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'dark' || stored === 'light') return stored
    return systemPrefersDark() ? 'dark' : 'light'
  })

  // Keep the <html> class in sync with state.
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  // Follow system changes only while no explicit choice is stored.
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    function onChange(e) {
      if (localStorage.getItem(STORAGE_KEY)) return
      setTheme(e.matches ? 'dark' : 'light')
    }
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  const toggle = useCallback(() => {
    setTheme((prev) => {
      const next = prev === 'dark' ? 'light' : 'dark'
      localStorage.setItem(STORAGE_KEY, next)
      return next
    })
  }, [])

  return { theme, toggle }
}
