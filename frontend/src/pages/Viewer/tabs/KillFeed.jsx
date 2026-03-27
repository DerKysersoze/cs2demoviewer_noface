import { useState, useMemo } from 'react'
import styles from '../Viewer.module.css'

export default function KillFeed({ kills }) {
  const [search,      setSearch]      = useState('')
  const [roundFilter, setRoundFilter] = useState('')

  const uniqueRounds = useMemo(() =>
    [...new Set(kills.map(k => k.round_num))].sort((a, b) => a - b),
    [kills]
  )

  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    return kills.filter(k => {
      const matchText  = !q ||
        k.attacker.toLowerCase().includes(q) ||
        k.victim.toLowerCase().includes(q)   ||
        k.weapon.toLowerCase().includes(q)
      const matchRound = !roundFilter || String(k.round_num) === roundFilter
      return matchText && matchRound
    })
  }, [kills, search, roundFilter])

  return (
    <>
      <div className={styles.killControls}>
        <input
          type="text"
          placeholder="Search player or weapon…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <select value={roundFilter} onChange={e => setRoundFilter(e.target.value)}>
          <option value="">All rounds</option>
          {uniqueRounds.map(r => (
            <option key={r} value={r}>Round {r}</option>
          ))}
        </select>
        <span className={styles.killCount}>{filtered.length} kills</span>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Tick</th>
              <th>Rnd</th>
              <th>Attacker</th>
              <th></th>
              <th>Victim</th>
              <th>Weapon</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((k, i) => {
              const isCt = k.attacker_team.toUpperCase().includes('CT')
              return (
                <tr key={i}>
                  <td className="muted">{k.tick}</td>
                  <td className="muted">{k.round_num}</td>
                  <td className={isCt ? styles.ctColor : styles.tColor}>
                    <strong>{k.attacker}</strong>
                  </td>
                  <td>
                    {k.headshot && <span className="badge" style={{ background:'rgba(250,204,21,.15)', color:'#facc15' }}>HS</span>}
                  </td>
                  <td style={{ color: 'var(--red)' }}>{k.victim}</td>
                  <td style={{ color: 'var(--green)' }}>{k.weapon}</td>
                  <td style={{ display: 'flex', gap: 4 }}>
                    {k.through_smoke && <span className="badge badge-note">smoke</span>}
                    {k.no_scope      && <span className="badge badge-note">no-scope</span>}
                    {k.penetrated    && <span className="badge badge-note">wall</span>}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </>
  )
}
