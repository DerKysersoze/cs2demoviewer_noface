import MicroLabel from '../../components/ui/MicroLabel'
import DotText from '../../components/ui/DotText'
import PlayerLink from './PlayerLink'
import { fmtClock, reasonIcon } from './format'
import styles from './Results.module.css'

function TeamName({ team, name, steamid }) {
  if (!name) return null
  const isCt = typeof team === 'string' && team.toUpperCase().includes('CT')
  return (
    <span className={styles.playerCell}>
      <span
        className={`${styles.teamDot} ${isCt ? styles.dotSolid : styles.dotOutline}`}
        aria-hidden="true"
      />
      <PlayerLink name={name} steamid={steamid} className="link-underline" />
    </span>
  )
}

/**
 * RoundStory — the selected round's story (reference "RoundDetail"):
 * header (ROUND N / winner / reason / start time + duration) and the
 * kill feed (`time · killer → weapon → victim [badges] assist: …` with
 * start/end divider rows).
 *
 * The 2D-map CTA deliberately lives on the RoundMap band below ("Open
 * fullscreen map"), not here — in-place replay and full-page replay stay
 * together.
 *
 * Times are round-relative: (kill.tick − round.start_tick) / tickrate.
 */
export default function RoundStory({ round, kills = [], tickrate = 128, players = {} }) {
  const list = kills
    .filter((k) => k.round_num === round.round_num)
    .sort((a, b) => a.tick - b.tick)

  const startTick = round.start_tick ?? null
  const endTick = round.end_tick ?? null
  const tSec = (tick) =>
    startTick != null && tick != null ? (tick - startTick) / tickrate : null
  const durSec =
    startTick != null && endTick != null ? (endTick - startTick) / tickrate : null

  return (
    <div className={styles.story}>
      <div className={styles.storyHead}>
        <div>
          <MicroLabel className={styles.metaLine}>ROUND {round.round_num}</MicroLabel>
          <DotText as="h3" className={styles.storyTitle}>
            {round.winner_side} win
          </DotText>
        </div>
        <div className={styles.storyMeta}>
          <p className={styles.storyReason}>{round.reason || '—'}</p>
          <p className={styles.metaLine}>
            {startTick != null ? `starts at ${fmtClock(startTick / tickrate)}` : '—'}
            {durSec != null ? ` · ${Math.round(durSec)}s` : ''}
          </p>
        </div>
      </div>

      <div>
        <MicroLabel className={styles.blockLabel}>KILL FEED</MicroLabel>
        <ol className={styles.feed}>
          <li className={styles.feedDivider}>
            <span>round start</span>
          </li>
          {list.length === 0 && (
            <li className={styles.metaLine}>No kills recorded in this round.</li>
          )}
          {list.map((k, i) => (
            <li key={i} className={styles.feedRow}>
              <span className={styles.feedTime}>
                {tSec(k.tick) != null ? fmtClock(tSec(k.tick)) : '—'}
              </span>
              <TeamName team={k.attacker_team} name={k.attacker} steamid={players[k.attacker]} />
              <span className={styles.feedArrow} aria-hidden="true">→</span>
              <span className={styles.feedWeapon}>{k.weapon}</span>
              <span className={styles.feedArrow} aria-hidden="true">→</span>
              <TeamName team={k.victim_team} name={k.victim} steamid={players[k.victim]} />
              {k.headshot && <span className={styles.badgeSolid}>HS</span>}
              {k.through_smoke && <span className={styles.badgeGhost}>SMOKE</span>}
              {k.penetrated && <span className={styles.badgeGhost}>WALL</span>}
              {k.no_scope && <span className={styles.badgeGhost}>NO SCOPE</span>}
              {k.assister && (
                <span className={styles.feedAssist}>
                  assist: <PlayerLink name={k.assister} steamid={players[k.assister]} className="link-underline" />
                </span>
              )}
            </li>
          ))}
          <li className={styles.feedDivider}>
            <span>
              {reasonIcon(round.reason)} {round.reason || 'round end'}
            </span>
          </li>
        </ol>
      </div>
    </div>
  )
}
