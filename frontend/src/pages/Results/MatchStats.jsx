import { Fragment, useMemo, useState } from 'react'
import MicroLabel from '../../components/ui/MicroLabel'
import PlayerLink from './PlayerLink'
import styles from './Results.module.css'

const COLUMNS = [
  { key: 'name',    label: 'PLAYER', align: 'left',  sortable: true  },
  { key: 'kills',   label: 'K',      align: 'right', sortable: true  },
  { key: 'deaths',  label: 'D',      align: 'right', sortable: true  },
  { key: 'assists', label: 'A',      align: 'right', sortable: true  },
  { key: 'kd',      label: 'K/D',    align: 'right', sortable: true  },
  { key: 'adr',     label: 'ADR',    align: 'right', sortable: true  },
  { key: 'kast',    label: 'KAST',   align: 'right', sortable: true  },
  { key: 'dmg',     label: 'DMG',    align: 'right', sortable: true  },
  { key: 'hs_pct',  label: 'HS%',    align: 'right', sortable: true  },
]

const isCt = (t = '') => typeof t === 'string' && t.toUpperCase().includes('CT')

/**
 * MatchStats — full-match sortable player table, upgraded for the redesigned
 * Overview tab:
 *
 *   - grouped into CT / T sections (sorting applies within each team)
 *   - MVP badge on the match's best player (same rule as the Players tab)
 *   - ADR column: average damage per round (total DMG ÷ rounds played)
 *   - KAST column (from the aim breakdown, matched by name)
 *   - DMG with an inline bar scaled to the match maximum — magnitude at a
 *     glance, HLTV-style
 *   - a ● best-of-match marker on the top value per column (K, K/D, KAST,
 *     DMG, HS%)
 *   - team totals rows under each team block (Σ K/D/A, team K/D, team KAST,
 *     Σ DMG, team HS%)
 *   - K/D colouring per the existing kd-good (≥ 1) / kd-bad (< 1) convention
 *
 * The extra data arrives precomputed (deriveOverview + scoreboard/aim).
 *
 * Player names are jump buttons: clicking one opens the Players tab with
 * that player's dossier (via `onPlayerClick`). Without the prop the names
 * fall back to PlayerLink (Steam profile).
 */
export default function MatchStats({ scoreboard = [], totalRounds = 0, kastByName = {}, topName = null, best = {}, onPlayerClick = null }) {
  const [sort, setSort] = useState({ key: 'kills', dir: -1 })

  const enriched = useMemo(() => {
    return scoreboard.map((p) => ({
      ...p,
      kdVal: p.deaths > 0 ? p.kills / p.deaths : p.kills,
      kast:  p.name in kastByName ? kastByName[p.name] : null,
      adr:   totalRounds > 0 ? (p.dmg ?? 0) / totalRounds : null,
    }))
  }, [scoreboard, kastByName, totalRounds])

  const groups = useMemo(() => {
    const byTeam = { CT: [], T: [] }
    for (const p of enriched) (isCt(p.team) ? byTeam.CT : byTeam.T).push(p)
    const val = (p) => {
      if (sort.key === 'kd')   return p.kdVal
      if (sort.key === 'kast') return p.kast ?? -1
      const v = p[sort.key]
      return v
    }
    const cmp = (a, b) => {
      const av = val(a)
      const bv = val(b)
      if (typeof av === 'string' && typeof bv === 'string') {
        return av.localeCompare(bv) * sort.dir
      }
      return ((av ?? -Infinity) - (bv ?? -Infinity)) * sort.dir
    }
    return { CT: byTeam.CT.sort(cmp), T: byTeam.T.sort(cmp) }
  }, [enriched, sort])

  function toggle(key) {
    setSort((s) => (s.key === key ? { key, dir: -s.dir } : { key, dir: -1 }))
  }

  const maxDmg = useMemo(
    () => Math.max(0, ...enriched.map((p) => p.dmg ?? 0)),
    [enriched]
  )

  const sections = [
    { key: 'CT', name: 'Counter-Terrorists' },
    { key: 'T',  name: 'Terrorists'         },
  ]

  /** Best-of-match marker for the given column (rendered before the value). */
  const bestDot = (colKey, p) =>
    best[colKey] && best[colKey] === p.name ? (
      <span className={styles.bestdot} aria-hidden="true" />
    ) : null

  const totalsRow = (key, rows) => {
    const k = rows.reduce((s, p) => s + (p.kills ?? 0), 0)
    const d = rows.reduce((s, p) => s + (p.deaths ?? 0), 0)
    const a = rows.reduce((s, p) => s + (p.assists ?? 0), 0)
    const dmg = rows.reduce((s, p) => s + (p.dmg ?? 0), 0)
    const hsEst = rows.reduce((s, p) => s + Math.round((p.kills ?? 0) * (p.hs_pct ?? 0) / 100), 0)
    const kasts = rows.map((p) => p.kast).filter((v) => v != null)
    return (
      <tr className={styles.totalsRow}>
        <td className="l"><MicroLabel>team totals</MicroLabel></td>
        <td className="r">{k}</td>
        <td className="r">{d}</td>
        <td className="r">{a}</td>
        <td className="r">{d > 0 ? (k / d).toFixed(2) : k}</td>
        <td className="r">{totalRounds > 0 ? Math.round(dmg / totalRounds) : '—'}</td>
        <td className="r">{kasts.length ? `${Math.round(kasts.reduce((s, v) => s + v, 0) / kasts.length)}%` : '—'}</td>
        <td className="r">
          <span className={styles.dmgCell}>
            {dmg.toLocaleString()}
            <span className={styles.dmgBar} aria-hidden="true">
              <i style={{ width: maxDmg ? `${(100 * dmg) / maxDmg}%` : '0%' }} />
            </span>
          </span>
        </td>
        <td className="r">{k ? `${Math.round((100 * hsEst) / k)}%` : '0%'}</td>
      </tr>
    )
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {COLUMNS.map((c) => (
              <th key={c.key} className={c.align === 'right' ? 'r' : 'l'}>
                {c.sortable ? (
                  <button
                    type="button"
                    className={styles.sortBtn}
                    onClick={() => toggle(c.key)}
                    aria-label={`Sort by ${c.label}`}
                  >
                    {c.label}
                    {sort.key === c.key ? (sort.dir === -1 ? ' ↓' : ' ↑') : ''}
                  </button>
                ) : (
                  c.label
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sections.map((sec) => (
            <Fragment key={sec.key}>
              <tr>
                <td colSpan={COLUMNS.length} className={styles.teamRowCell}>
                  <span className={`${styles.teamDot} ${styles.dotSolid}`} aria-hidden="true" />
                  <MicroLabel>{sec.name}</MicroLabel>
                </td>
              </tr>
              {groups[sec.key].map((p) => (
                <tr key={`${p.name}|${p.steamid || ''}`}>
                  <td className="l">
                    <span className={styles.playerCell}>
                      <span
                        className={`${styles.teamDot} ${
                          sec.key === 'CT' ? styles.dotSolid : styles.dotOutline
                        }`}
                        aria-hidden="true"
                      />
                      {onPlayerClick ? (
                        <button
                          type="button"
                          className="steam-link name-jump link-underline"
                          onClick={() => onPlayerClick(p.name)}
                        >
                          {p.name}
                          <span className="steam-hint" aria-hidden="true">players →</span>
                        </button>
                      ) : (
                        <PlayerLink name={p.name} steamid={p.steamid} className="link-underline" />
                      )}
                      {p.name === topName && <span className={styles.mvpTag}>MVP</span>}
                    </span>
                  </td>
                  <td className="r">
                    {bestDot('kills', p)}
                    <span className={best.kills === p.name ? styles.bestVal : undefined}>{p.kills}</span>
                  </td>
                  <td className="r">{p.deaths}</td>
                  <td className="r">{p.assists}</td>
                  <td className="r">
                    {bestDot('kd', p)}
                    <span
                      className={
                        (p.kdVal >= 1 ? 'kd-good ' : 'kd-bad ') +
                        (best.kd === p.name ? styles.bestVal : '')
                      }
                    >
                      {p.kdVal.toFixed(2)}
                    </span>
                  </td>
                  <td className="r">
                    {/* No best-dot: ADR ranks identically to DMG (same divisor). */}
                    {p.adr != null ? (
                      Math.round(p.adr)
                    ) : (
                      <span className={styles.cellMuted}>—</span>
                    )}
                  </td>
                  <td className="r">
                    {bestDot('kast', p)}
                    {p.kast != null ? (
                      <span className={best.kast === p.name ? styles.bestVal : undefined}>{p.kast}</span>
                    ) : (
                      <span className={styles.cellMuted}>—</span>
                    )}
                  </td>
                  <td className="r">
                    <span className={styles.dmgCell}>
                      <span className={best.dmg === p.name ? styles.bestVal : undefined}>
                        {bestDot('dmg', p)}
                        {(p.dmg ?? 0).toLocaleString()}
                      </span>
                      <span className={styles.dmgBar} aria-hidden="true">
                        <i style={{ width: maxDmg ? `${(100 * (p.dmg ?? 0)) / maxDmg}%` : '0%' }} />
                      </span>
                    </span>
                  </td>
                  <td className="r">
                    {bestDot('hs_pct', p)}
                    <span className={best.hs_pct === p.name ? styles.bestVal : undefined}>
                      {Math.round(p.hs_pct ?? 0)}%
                    </span>
                  </td>
                </tr>
              ))}
              {totalsRow(sec.key, groups[sec.key])}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  )
}
