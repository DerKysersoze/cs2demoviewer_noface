import { reasonIcon } from './format'
import styles from './Results.module.css'

const REASON_TEXT = {
  'Bomb Exploded': 'bomb exploded',
  'Bomb Defused':  'bomb defused',
  'Ct Killed':     'CT eliminated',
  'T Killed':      'T eliminated',
  'Time Ran Out':  'time ran out',
}

/**
 * FlowStrip — the match's round-by-round flow: one segment per round,
 * solid ink = CT won, outlined = T won, with the round's end-reason icon
 * (💣 bomb · 🛠 defuse · ☠ elimination · ⏱ timeout). The MR12 half break is
 * marked between the halves. Hover shows "R5 · T · bomb exploded"; clicking
 * a segment selects that round (the caller switches to the Rounds tab via
 * jumpToRound, so the user lands on the story).
 *
 * Data arrives precomputed from deriveOverview (rounds[].winner_side + reason).
 */
export default function FlowStrip({ flow = [], onJump }) {
  if (!flow.length) return null

  const jump = (num) => onJump && onJump(num)

  return (
    <div>
      <div className={styles.flow} role="list" aria-label="Round-by-round winners">
        {flow.map((r) => (
          <span key={r.num} className={styles.flowCell}>
            {r.halfBefore && (
              <span className={styles.halfMark} aria-hidden="true">HALF</span>
            )}
            <button
              type="button"
              role="listitem"
              className={`${styles.seg} ${r.winner === 'T' ? styles.segT : styles.segCt}`}
              title={`R${r.num} · ${r.winner === 'T' ? 'T' : 'CT'} · ${REASON_TEXT[r.reason] || r.reason || 'round'}`}
              aria-label={`Round ${r.num}, won by ${r.winner === 'T' ? 'T' : 'CT'}. ${REASON_TEXT[r.reason] || r.reason}. Open this round.`}
              onClick={() => jump(r.num)}
            >
              {reasonIcon(r.reason) || '·'}
            </button>
          </span>
        ))}
      </div>

      <div className={styles.flowLegend}>
        <span className={styles.legendItem}>
          <span className={`${styles.legendSw} ${styles.dotSolid}`} aria-hidden="true" />
          CT won the round
        </span>
        <span className={styles.legendItem}>
          <span className={`${styles.legendSw} ${styles.dotOutline}`} aria-hidden="true" />
          T won the round
        </span>
        <span className={styles.legendItem}>
          💣 bomb exploded · 🛠 defused · ☠ eliminated · ⏱ timeout
        </span>
      </div>
    </div>
  )
}
