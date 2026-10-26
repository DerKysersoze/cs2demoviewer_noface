import MicroLabel from '../../components/ui/MicroLabel'
import PlayerLink from './PlayerLink'
import { fmtClock } from './format'
import styles from './Results.module.css'

const TYPE_ICON = {
  'multi-kill': '🔥',
  clutch:       '🎯',
  defuse:       '🛠',
  bomb:         '💣',
  'top-damage': '⚡',
  streak:       '📈',
}

/**
 * Highlights — auto-detected moments (see deriveHighlights), each linked to
 * its round. Match-wide entries (top damage) render disabled, like the
 * reference's no-round items.
 *
 * Player names render as Steam community profile links (new tab). The card
 * itself stays click-to-jump; it's a div (not a button) so the nested
 * anchors are valid HTML, with Enter/Space keyboard support preserved.
 */
export default function Highlights({ highlights = [], onJump }) {
  return (
    <div>
      <MicroLabel className={styles.blockLabel}>HIGHLIGHTS</MicroLabel>
      {highlights.length === 0 ? (
        <p className={styles.metaLine}>No highlights detected for this match.</p>
      ) : (
        <ul className={styles.hGrid}>
          {highlights.map((h, i) => (
            <li key={i}>
              <div
                className={`${styles.hItem}${h.round ? '' : ' ' + styles.hItemDisabled}`}
                role={h.round ? 'button' : undefined}
                tabIndex={h.round ? 0 : -1}
                aria-disabled={h.round ? undefined : true}
                onClick={() => h.round && onJump(h.round)}
                onKeyDown={(e) => {
                  if (!h.round) return
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    onJump(h.round)
                  }
                }}
              >
                <span className={styles.hIcon} aria-hidden="true">
                  {TYPE_ICON[h.type] || '•'}
                </span>
                <span className={styles.hText}>
                  <span className={styles.hTitle}>
                    {h.player && h.player.in === 'title' && (
                      <PlayerLink name={h.player.name} steamid={h.player.steamid} className="link-underline" />
                    )}
                    {h.player && h.player.in === 'title' && '\u00A0'}
                    {h.title}
                  </span>
                  <span className={styles.hDetail}>
                    {h.player && h.player.in === 'detail' && (
                      <PlayerLink name={h.player.name} steamid={h.player.steamid} className="link-underline" />
                    )}
                    {h.player && h.player.in === 'detail' && '\u00A0'}
                    {h.detail}
                    {h.timeSec != null && ` · ${fmtClock(h.timeSec)}`}
                  </span>
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
