import { steamUrl } from './format'

/**
 * PlayerLink — a player's display name, linked to their Steam community
 * profile when a valid SteamID64 is known (opens in a new tab); plain
 * text otherwise (e.g. names the parser couldn't resolve to an id).
 *
 * Hovering (or keyboard-focusing) the name fades in a small "steam ↗" pill
 * above it — `.steam-hint` in index.css. The pill is absolutely positioned,
 * so it floats over the layout instead of pushing inline content (the name
 * is often the last text in a narrow card, e.g. the Rounds-tab kill feed).
 *
 * className is applied to the anchor/span so callers keep control of
 * styling — pass `link-underline` for the design-system hover underline.
 */
export default function PlayerLink({ name, steamid, className }) {
  const url = steamUrl(steamid)
  if (!url) return <span className={className}>{name}</span>
  const cls = className
    ? `steam-link ${className}`
    : 'steam-link'
  return (
    <a
      className={cls}
      href={url}
      target="_blank"
      rel="noreferrer noopener"
    >
      {name}
      <span className="steam-hint" aria-hidden="true">steam ↗</span>
    </a>
  )
}
