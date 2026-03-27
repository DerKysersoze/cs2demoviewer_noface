import styles from './Admin.module.css'

function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

export default function ResultsTable({ result }) {
  if (!result) {
    return <div className={styles.resultsEmpty}>Run a query to see results.</div>
  }

  if (result.error) {
    return <div className={`${styles.resultsEmpty} ${styles.errText}`}>Error: {result.error}</div>
  }

  if (!result.columns?.length) {
    return <div className={styles.resultsEmpty}>Query executed successfully — no rows returned.</div>
  }

  return (
    <table className={styles.resultsTable}>
      <thead>
        <tr>
          {result.columns.map(col => <th key={col}>{col}</th>)}
        </tr>
      </thead>
      <tbody>
        {result.rows.map((row, ri) => (
          <tr key={ri}>
            {row.map((cell, ci) => {
              if (cell === null || cell === undefined) {
                return <td key={ci} className={styles.nullCell}>NULL</td>
              }
              const s = String(cell)
              const display = s.length > 300 ? s.slice(0, 300) + '…' : s
              return (
                <td key={ci} title={s.length > 60 ? s.slice(0, 500) : undefined}>
                  {display}
                </td>
              )
            })}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
