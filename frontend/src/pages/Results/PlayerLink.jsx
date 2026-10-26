import { steamUrl } from './format'

/**
 * PlayerLink — a player's display name, linked to their Steam community
 * profile when a valid SteamID64 is known (opens in a new tab); plain
 * text otherwise (e.g. names the parser couldn't resolve to an id).
 *
 * Hovering (or keyboard-focusing) the name fades in a small
 * "open steam profile" hint to its right — see `.steam-hint` in index.css.
 *
 * className is applied to the anchor/span so callers keep control of
 * styling — pass `link-underline` for the design-system hover underline.
 */
export default function PlayerLink({ name, steamid, className }) {
  const url = steamUrl(steamid)
  if (!url) return <span className={className}>{name}</span>
  return (
    <a
      className={className}
      href={url}
      target="_blank"
      rel="noreferrer noopener"
    >
      {name}
      <span className="steam-hint" aria-hidden="true">open steam profile</span>
    </a>
  )
}
