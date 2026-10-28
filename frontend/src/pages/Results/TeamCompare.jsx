import MicroLabel from '../../components/ui/MicroLabel'
import PlayerLink from './PlayerLink'
import styles from './Results.module.css'

/**
 * TeamCompare — the Overview tab's "team at a glance" band: CT and T side by
 * side with the aggregates that answer "who was the better team, and why" —
 * rounds won, total DMG, team HS %, team KAST and the team's MVP (best
 * player of the side, same rule as the match MVP badge).
 *
 * The winner's card carries the solid border + WINNER badge (the same
 * solid-vs-outlined CT/T language as the header's winner badge).
 * All data arrives precomputed from deriveOverview.
 *
 * The team MVP name is a jump button into the Players tab when
 * `onPlayerClick` is provided (Steam profile link otherwise).
 */
export default function TeamCompare({ teams, onPlayerClick = null }) {
  if (!teams) return null
  const cards = [teams.CT, teams.T]

  return (
    <div className={styles.glance}>
      {cards.map((t) => (
        <div
          key={t.key}
          className={`${styles.tcard}${t.winner ? ' ' + styles.tcardWinner : ''}`}
        >
          <div className={styles.tcardHead}>
            <span className={styles.tchip}>
              <span
                className={`${styles.tchipSwatch} ${t.key === 'CT' ? styles.dotSolid : styles.dotOutline}`}
                aria-hidden="true"
              />
              {t.key === 'CT' ? 'CT' : 'T'}
            </span>
            {t.winner && <span className={styles.glanceBadge}>Winner</span>}
          </div>

          <div className={styles.tcardStats}>
            <div>
              <span className={styles.tsVal}>{t.wins}</span>
              <span className={styles.tsLbl}>rounds won</span>
            </div>
            <div>
              <span className={styles.tsVal}>{(t.dmg ?? 0).toLocaleString()}</span>
              <span className={styles.tsLbl}>total DMG</span>
            </div>
            <div>
              <span className={styles.tsVal}>{t.hsPct}%</span>
              <span className={styles.tsLbl}>HS %</span>
            </div>
            <div>
              <span className={styles.tsVal}>{t.kast != null ? `${t.kast}%` : '—'}</span>
              <span className={styles.tsLbl}>KAST</span>
            </div>
          </div>

          {t.mvp && (
            <div className={styles.tcardFoot}>
              <MicroLabel>mvp</MicroLabel>
              {onPlayerClick ? (
                <button
                  type="button"
                  className="steam-link name-jump link-underline"
                  onClick={() => onPlayerClick(t.mvp.name)}
                >
                  {t.mvp.name}
                  <span className="steam-hint" aria-hidden="true">players →</span>
                </button>
              ) : (
                <PlayerLink name={t.mvp.name} steamid={t.mvp.steamid} className="link-underline" />
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
