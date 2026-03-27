import styles from '../Viewer.module.css'

export default function Rounds({ rounds }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Winner</th>
            <th>Reason</th>
            <th className="r">CT Score</th>
            <th className="r">T Score</th>
          </tr>
        </thead>
        <tbody>
          {rounds.map(r => {
            const isCt = r.winner_side.toUpperCase().includes('CT')
            return (
              <tr key={r.round_num} className={isCt ? styles.ctWinRow : styles.tWinRow}>
                <td>{r.round_num}</td>
                <td>
                  <span className={`badge ${isCt ? 'badge-ct' : 'badge-t'}`}>
                    {r.winner_side} Win
                  </span>
                </td>
                <td>{r.reason}</td>
                <td className={`r ${styles.ctColor}`}>{r.ct_score}</td>
                <td className={`r ${styles.tColor}`}>{r.t_score}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
