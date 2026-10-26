import { Fragment, useMemo, useState } from 'react'
import MicroLabel from '../../components/ui/MicroLabel'
import PlayerLink from './PlayerLink'
import styles from './Results.module.css'

const COLUMNS = [
  { key: 'name',    label: 'PLAYER', align: 'left' },
  { key: 'kills',   label: 'K',      align: 'right' },
  { key: 'deaths',  label: 'D',      align: 'right' },
  { key: 'assists', label: 'A',      align: 'right' },
  { key: 'kd',      label: 'K/D',    align: 'right' },
  { key: 'dmg',     label: 'DMG',    align: 'right' },
  { key: 'hs_pct',  label: 'HS%',    align: 'right' },
]

/**
 * MatchStats — full-match sortable player table.
 * Players are grouped into CT / T sections with a labeled divider row between
 * the teams; sorting applies within each team (like the reference).
 * UTIL and MVP columns from the reference are dropped — not parsed here.
 */
export default function MatchStats({ scoreboard = [] }) {
  const [sort, setSort] = useState({ key: 'kills', dir: -1 })

  const groups = useMemo(() => {
    const enriched = scoreboard.map((p) => ({
      ...p,
      kd: p.deaths > 0 ? p.kills / p.deaths : p.kills,
    }))
    const byTeam = { CT: [], T: [] }
    for (const p of enriched) {
      const isCt = typeof p.team === 'string' && p.team.toUpperCase().includes('CT')
      ;(isCt ? byTeam.CT : byTeam.T).push(p)
    }
    const cmp = (a, b) => {
      const av = a[sort.key]
      const bv = b[sort.key]
      if (typeof av === 'string') return av.localeCompare(bv) * sort.dir
      return ((av ?? 0) - (bv ?? 0)) * sort.dir
    }
    return { CT: byTeam.CT.sort(cmp), T: byTeam.T.sort(cmp) }
  }, [scoreboard, sort])

  function toggle(key) {
    setSort((s) => (s.key === key ? { key, dir: -s.dir } : { key, dir: -1 }))
  }

  const sections = [
    { key: 'CT', name: 'Counter-Terrorists', accent: false },
    { key: 'T',  name: 'Terrorists',         accent: true  },
  ]

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {COLUMNS.map((c) => (
              <th key={c.key} className={c.align === 'right' ? 'r' : ''}>
                <button
                  type="button"
                  className={styles.sortBtn}
                  onClick={() => toggle(c.key)}
                  aria-label={`Sort by ${c.label}`}
                >
                  {c.label}
                  {sort.key === c.key ? (sort.dir === -1 ? ' ↓' : ' ↑') : ''}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sections.map((sec) => (
            <Fragment key={sec.key}>
              <tr className={sec.accent ? styles.teamRowAccent : undefined}>
                <td colSpan={COLUMNS.length} className={styles.teamRowCell}>
                  <span className={`${styles.teamDot} ${styles.dotSolid}`} aria-hidden="true" />
                  <MicroLabel>{sec.name}</MicroLabel>
                </td>
              </tr>
              {groups[sec.key].map((p) => (
                <tr key={`${p.name}|${p.steamid || ''}`}>
                  <td>
                    <span className={styles.playerCell}>
                      <span
                        className={`${styles.teamDot} ${
                          sec.key === 'CT' ? styles.dotSolid : styles.dotOutline
                        }`}
                        aria-hidden="true"
                      />
                      <PlayerLink name={p.name} steamid={p.steamid} className="link-underline" />
                    </span>
                  </td>
                  <td className="r">{p.kills}</td>
                  <td className="r">{p.deaths}</td>
                  <td className="r">{p.assists}</td>
                  <td className="r">{p.kd.toFixed(2)}</td>
                  <td className="r">{(p.dmg ?? 0).toLocaleString()}</td>
                  <td className="r">{Math.round(p.hs_pct ?? 0)}%</td>
                </tr>
              ))}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  )
}
