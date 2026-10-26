import MicroLabel from '../../components/ui/MicroLabel'
import DotText from '../../components/ui/DotText'
import { prettifyMap } from './format'
import styles from './Results.module.css'

/**
 * MatchHeader — the reference's header band: micro-label + giant dot-text map
 * name on the left; giant dot-text score, "N rounds · duration", and the
 * winner badge (CT WIN solid ink / T WIN outlined / DRAW grey) on the right.
 */
export default function MatchHeader({ d }) {
  const h = d.header || {}
  const ct = d.ct_wins ?? 0
  const t = d.t_wins ?? 0
  const winner = ct > t ? 'CT' : t > ct ? 'T' : 'DRAW'

  return (
    <div className={styles.header}>
      <div>
        <MicroLabel className={styles.metaLine}>{d.filename || 'unknown demo'}</MicroLabel>
        <DotText as="h1" className={styles.mapName}>{prettifyMap(h.map)}</DotText>
      </div>
      <div className={styles.headerRight}>
        <div className={styles.headerRightText}>
          <p className={styles.score}>{ct} — {t}</p>
          <p className={styles.metaLine}>
            {d.total_rounds} rounds · {h.duration || '—'}
          </p>
        </div>
        <span
          className={`${styles.winnerBadge} ${
            winner === 'CT' ? styles.winnerCt : winner === 'T' ? styles.winnerT : styles.winnerDraw
          }`}
        >
          {winner === 'CT' ? 'CT WIN' : winner === 'T' ? 'T WIN' : 'DRAW'}
        </span>
      </div>
    </div>
  )
}
