import MicroLabel from '../../components/ui/MicroLabel'
import PlayerLink from './PlayerLink'
import styles from './Results.module.css'

const GROUPS = [
  { types: ['clutch'],                 icon: '🎯', label: 'Clutch' },
  { types: ['multi-kill'],             icon: '🔥', label: 'Multi-kills' },
  { types: ['streak'],                 icon: '📈', label: 'Kill streaks' },
  { types: ['bomb', 'defuse'],         icon: '💣', label: 'Bomb & defuse' },
]

/** Compact per-item shorthand (the group header already says the type). */
function shortLabel(h) {
  const n = h.count
  switch (h.type) {
    case 'clutch':     return n ? `${n}K` : ''
    case 'multi-kill': return n === 2 ? 'double' : n === 3 ? 'triple'
                       : n === 4 ? 'quad' : n === 5 ? 'ace' : (n ? `${n}-kill` : '')
    case 'streak':     return n ? `${n}-kill run` : ''
    case 'bomb':       return h.winner === 'T' ? 'T took it' : 'CT took it'
    case 'defuse':     return h.winner === 'CT' ? 'CT took it' : 'T took it'
    default:           return ''
  }
}

/**
 * Highlights — the auto-detected moments (see deriveHighlights), now
 * grouped by type with a count per group so the page reads as "6 clutches,
 * 13 multi-kills, …" instead of a flat wall of cards.
 *
 * Each item renders the player (a jump button into the Players tab when
 * `onPlayerClick` is provided — it stops propagation, so the rest of the
 * row still selects the round — or a Steam community profile link), a
 * compact label (4K / double / 3-kill run / T took it) and a round chip —
 * clicking the item (or pressing Enter/Space) selects that round and
 * switches to the Rounds tab.
 *
 * The player-name jump carries a `title` tooltip instead of the floating
 * hint pill: the name cell is ellipsised (overflow hidden), which would
 * clip the pill.
 *
 * "Top damage" entries are intentionally dropped: the scoreboard's DMG bars,
 * ● best-of-match markers and MVP badge surface that data directly.
 */
export default function Highlights({ highlights = [], onJump, onPlayerClick = null }) {
  const groups = GROUPS.map((g) => ({
    ...g,
    items: highlights.filter((h) => g.types.includes(h.type)),
  })).filter((g) => g.items.length > 0)

  if (groups.length === 0) {
    return (
      <div>
        <MicroLabel className={styles.blockLabel}>MOMENTS</MicroLabel>
        <p className={styles.metaLine}>No highlights detected for this match.</p>
      </div>
    )
  }

  const jump = (num) => onJump && onJump(num)

  return (
    <div>
      <MicroLabel className={styles.blockLabel}>MOMENTS</MicroLabel>
      <div className={styles.moments}>
        {groups.map((g) => (
          <div key={g.label} className={styles.mgroup}>
            <h4 className={styles.mgroupHead}>
              <span aria-hidden="true">{g.icon}</span>
              {g.label}
              <span className={styles.mcount}>×{g.items.length}</span>
            </h4>
            <ul className={styles.mlist}>
              {g.items.map((h, i) => (
                <li key={i}>
                  <div
                    className={styles.mitem}
                    role="button"
                    tabIndex={0}
                    onClick={() => h.round && jump(h.round)}
                    onKeyDown={(e) => {
                      if (!h.round) return
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        jump(h.round)
                      }
                    }}
                  >
                    <span className={styles.mname}>
                      {h.player ? (
                        onPlayerClick ? (
                          <button
                            type="button"
                            className="name-jump link-underline"
                            title="View stats in the Players tab"
                            onClick={(e) => {
                              e.stopPropagation()
                              onPlayerClick(h.player.name)
                            }}
                          >
                            {h.player.name}
                          </button>
                        ) : (
                          <PlayerLink name={h.player.name} steamid={h.player.steamid} className="link-underline" />
                        )
                      ) : (
                        h.title
                      )}
                    </span>
                    <span className={styles.mlabel}>{shortLabel(h)}</span>
                    <span className={styles.mround} aria-hidden="true">R{h.round} →</span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}
