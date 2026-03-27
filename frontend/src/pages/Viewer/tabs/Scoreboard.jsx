import styles from '../Viewer.module.css'

function PlayerName({ name, steamid }) {
  if (!steamid) return <strong>{name}</strong>
  return (
    <strong>
      <a
        href={`https://steamcommunity.com/profiles/${steamid}`}
        target="_blank"
        rel="noopener noreferrer"
        style={{ color: 'inherit', textDecoration: 'underline dotted', textUnderlineOffset: 3 }}
      >
        {name}
      </a>
    </strong>
  )
}

function ScoreTable({ label, color, players }) {
  return (
    <div className={styles.scoreboardSide}>
      <div className={styles.sideLabel} style={{ color }}>{label}</div>
      <div className="table-wrap" style={{ marginBottom: 0 }}>
        <table>
          <thead>
            <tr>
              <th>Player</th>
              <th className="r">K</th>
              <th className="r">A</th>
              <th className="r">D</th>
              <th className="r">K/D</th>
              <th className="r">HS%</th>
              <th className="r">DMG</th>
            </tr>
          </thead>
          <tbody>
            {players.map(p => {
              const kdClass = p.kd >= 1.1 ? 'kd-good' : p.kd < 0.9 ? 'kd-bad' : 'kd-even'
              return (
                <tr key={p.name}>
                  <td><PlayerName name={p.name} steamid={p.steamid} /></td>
                  <td className="r">{p.kills}</td>
                  <td className="r">{p.assists}</td>
                  <td className="r">{p.deaths}</td>
                  <td className={`r ${kdClass}`}>{p.kd.toFixed(2)}</td>
                  <td className="r">{p.hs_pct}%</td>
                  <td className="r">{p.dmg.toLocaleString()}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function Scoreboard({ scoreboard }) {
  const ct = scoreboard.filter(p => p.team.toUpperCase().includes('CT'))
  const t  = scoreboard.filter(p => !p.team.toUpperCase().includes('CT'))

  return (
    <div className={styles.scoreboardWrap}>
      <ScoreTable label="Counter-Terrorists" color="var(--ct)" players={ct} />
      <ScoreTable label="Terrorists"         color="var(--t)"  players={t} />
    </div>
  )
}
