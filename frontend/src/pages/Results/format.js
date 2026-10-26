/**
 * Formatting helpers for the Results page.
 * fmtClock mirrors the reference implementation; prettifyMap mirrors its
 * server-side map prettification (de_dust2 -> Dust II).
 */

export function fmtClock(sec) {
  if (!Number.isFinite(sec) || sec < 0) sec = 0
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

/** de_dust2 -> Dust II, de_nuke -> Nuke, de_inferno -> Inferno. */
export function prettifyMap(raw) {
  if (!raw) return 'Unknown map'
  const base = raw.replace(/^de_/, '').replace(/_/g, ' ')
  return base
    .split(' ')
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
    .join(' ')
}

/*
 * CS2 round reasons as stored in demo_rounds.reason (verified against the
 * demo in demos.db). Icons mirror the reference timeline: bomb, defuse,
 * elimination, timeout.
 */
export const REASON_ICON = {
  'Bomb Exploded': '💣',
  'Bomb Defused':  '🛠',
  'Ct Killed':     '☠',
  'T Killed':      '☠',
  'Time Ran Out':  '⏱',
}

export function reasonIcon(reason) {
  return REASON_ICON[reason] || ''
}

/**
 * SteamID64 -> steamcommunity.com profile URL.
 * Returns null when the value isn't a 17-digit SteamID64 (e.g. a killer
 * whose id the parser couldn't resolve) so callers fall back to plain text.
 */
export function steamUrl(steamid) {
  const s = String(steamid ?? '').trim()
  return /^\d{17}$/.test(s) ? `https://steamcommunity.com/profiles/${s}` : null
}
