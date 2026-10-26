import { useNavigate } from 'react-router-dom'
import styles from './Upload.module.css'

/** "977.8s" → "16:18" (the demos.duration format from the parser). */
function fmtDuration(s) {
  if (!s) return ''
  const n = parseFloat(String(s).replace(/s$/i, ''))
  if (!Number.isFinite(n) || n < 0) return ''
  const m = Math.floor(n / 60)
  const sec = Math.round(n % 60)
  return `${m}:${String(sec).padStart(2, '0')}`
}

/** "2026-10-26T16:33:40Z" → "OCT 26 · 09:33" (local time). */
function fmtWhen(str) {
  const ts = new Date(str)
  if (isNaN(ts)) return String(str)
  const d = ts.toLocaleDateString(undefined, { day: '2-digit', month: 'short' }).toUpperCase()
  const t = ts.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
  return `${d} · ${t}`
}

/**
 * Library card for the front page (mockup option A).
 * Base state: map image + map name, score line, winner badge, meta.
 * Hover/focus: quick-stats panel (top performer, rounds, duration, CTA)
 * slides up over the image; delete button appears.
 */
export default function DemoCard({ demo, onDelete }) {
  const navigate = useNavigate()
  const {
    id, map,
    ct_wins: ct, t_wins: t,
    total_rounds, duration, uploaded_at,
    mvp_name, mvp_team, mvp_kills, mvp_kd,
  } = demo

  const hasScore = ct != null && t != null
  const ctWin = hasScore && ct > t
  const tWin = hasScore && t > ct
  const hasMvp = Boolean(mvp_name)

  function open(e) {
    // Let the delete button (and any future interactive child) keep its own click.
    if (e.target.closest('button')) return
    navigate(`/results/${id}`)
  }

  function onKey(e) {
    if (e.target.closest('button')) return
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate(`/results/${id}`) }
  }

  return (
    <article
      className={styles.card}
      tabIndex={0}
      role="link"
      aria-label={`${map} — open results`}
      onClick={open}
      onKeyDown={onKey}
    >
      <div className={styles.cardImg}>
        <img
          src={`/api/map_image/${map}`}
          alt={`${map} map`}
          loading="lazy"
          onError={e => { e.currentTarget.style.display = 'none' }}
        />
        <span className={styles.cardMap}>{map}</span>
        <button
          type="button"
          className={styles.cardDel}
          title="Delete demo"
          aria-label={`Delete ${map}`}
          onClick={e => { e.stopPropagation(); onDelete() }}
        >
          ✕
        </button>

        <div className={styles.cardHover}>
          <span className="micro-label">Top performer</span>
          {hasMvp ? (
            <div className={styles.mvp}>
              <i className={mvp_team === 'CT' ? styles.dotCT : styles.dotT} />
              <strong>{mvp_name}</strong>
              <span className={styles.mvpStat}>
                {mvp_kills} kills{mvp_kd != null ? ` · K/D ${Number(mvp_kd).toFixed(2)}` : ''}
              </span>
            </div>
          ) : (
            <div className={styles.mvp}><span className={styles.mvpNone}>no data</span></div>
          )}
          <div className={styles.cardHoverFoot}>
            <span>
              {total_rounds ? `${total_rounds} rounds` : 'rounds n/a'}
              {duration ? ` · ${fmtDuration(duration)}` : ''}
            </span>
            <span className={styles.go}>Results →</span>
          </div>
        </div>
      </div>

      <div className={styles.cardBody}>
        <div className={styles.scoreline}>
          <span className={`${styles.side} ${ctWin ? styles.winCT : styles.lose}`}>
            <b className={styles.num}>{ct ?? '–'}</b>CT
          </span>
          <span className={`${styles.side} ${tWin ? styles.winT : styles.lose}`}>
            T<b className={styles.num}>{t ?? '–'}</b>
          </span>
          {hasScore && (
            ctWin
              ? <span className={`${styles.wbadge} ${styles.wbadgeCT}`}>CT WIN</span>
              : <span className={`${styles.wbadge} ${styles.wbadgeT}`}>T WIN</span>
          )}
        </div>
        <div className={styles.cardMeta}>
          {total_rounds ? `${total_rounds} ROUNDS` : 'ROUNDS N/A'}
          {` · ${duration ? fmtDuration(duration) : '—'}`}
          {` · ${fmtWhen(uploaded_at)}`}
        </div>
      </div>
    </article>
  )
}
