import MicroLabel from '../../components/ui/MicroLabel'
import { reasonIcon } from './format'
import styles from './Results.module.css'

/**
 * RoundChips — one 40×40 chip per round (reference "RoundTimeline").
 * Filled ink = CT win, outlined = T win, grey = draw; reason icon under the
 * number; the selected round is ringed. Horizontal scroll for long matches.
 */
export default function RoundChips({ rounds = [], selected, onSelect }) {
  return (
    <div>
      <div className={styles.chipHead}>
        <MicroLabel className={styles.metaLine}>ROUNDS</MicroLabel>
        <MicroLabel className={styles.metaLine}>{rounds.length} total</MicroLabel>
      </div>
      <div className={styles.chipRow} role="tablist" aria-label="Round selector">
        {rounds.map((r) => {
          const isSel = r.round_num === selected
          const fill =
            r.winner_side === 'CT' ? styles.chipCt :
            r.winner_side === 'T'  ? styles.chipT :
                                    styles.chipDraw
          return (
            <button
              key={r.round_num}
              type="button"
              role="tab"
              aria-selected={isSel}
              title={`Round ${r.round_num} — ${r.reason || 'unknown reason'}`}
              onClick={() => onSelect(r.round_num)}
              className={`${styles.chip} ${fill}${isSel ? ' ' + styles.chipSel : ''}`}
            >
              <span>{r.round_num}</span>
              <span className={styles.chipIcon} aria-hidden="true">
                {reasonIcon(r.reason)}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
