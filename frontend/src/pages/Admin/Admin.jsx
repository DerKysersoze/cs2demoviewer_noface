import { useState, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { adminApi } from '../../api/admin'
import SiteHeader from '../../components/SiteHeader'
import SchemaPanel from './SchemaPanel'
import ResultsTable from './ResultsTable'
import styles from './Admin.module.css'

export default function Admin() {
  const [sql, setSql]       = useState('')
  const [result, setResult] = useState(null)
  const [status, setStatus] = useState({ msg: '', type: 'dim' })
  const [running, setRunning] = useState(false)
  const textareaRef = useRef(null)

  const setQuery = useCallback((q) => {
    setSql(q)
    textareaRef.current?.focus()
  }, [])

  async function runQuery() {
    const trimmed = sql.trim()
    if (!trimmed) return
    setRunning(true)
    setStatus({ msg: 'Running…', type: 'dim' })
    try {
      const res = await adminApi.query(trimmed)
      if (res.error) {
        setStatus({ msg: `Error: ${res.error}`, type: 'err' })
        setResult({ error: res.error })
      } else {
        const msg = res.message
          ?? `${res.rowcount} row${res.rowcount !== 1 ? 's' : ''} — ${res.elapsed_ms} ms`
        setStatus({ msg, type: 'ok' })
        setResult(res)
      }
    } catch (err) {
      setStatus({ msg: `Network error: ${err.message}`, type: 'err' })
      setResult({ error: err.message })
    } finally {
      setRunning(false)
    }
  }

  function handleKey(e) {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault()
      runQuery()
    }
    if (e.key === 'Tab') {
      e.preventDefault()
      const el = e.target
      const s  = el.selectionStart
      setSql(v => v.slice(0, s) + '  ' + v.slice(el.selectionEnd))
      // restore cursor after state update
      requestAnimationFrame(() => {
        el.selectionStart = el.selectionEnd = s + 2
      })
    }
  }

  const statusClass = {
    ok:  styles.statusOk,
    err: styles.statusErr,
    dim: styles.statusDim,
  }[status.type]

  return (
    <>
      <SiteHeader>
        <Link to="/" className="btn btn-ghost" style={{ marginLeft: 'auto' }}>
          ← Back to app
        </Link>
      </SiteHeader>

      <div className={styles.layout}>
        <SchemaPanel onSelectQuery={setQuery} />

        <section className={styles.editorPanel}>
          <label className={styles.editorLabel}>SQL Query</label>

          <textarea
            ref={textareaRef}
            className={styles.sqlEditor}
            value={sql}
            onChange={e => setSql(e.target.value)}
            onKeyDown={handleKey}
            placeholder="SELECT * FROM demos LIMIT 10;"
            spellCheck={false}
          />

          <div className={styles.runBar}>
            <button
              className="btn btn-primary"
              onClick={runQuery}
              disabled={running}
            >
              ▶ Run
            </button>
            <button
              className="btn btn-ghost"
              onClick={() => { setSql(''); setResult(null); setStatus({ msg: '', type: 'dim' }) }}
            >
              Clear
            </button>
            {status.msg && <span className={statusClass}>{status.msg}</span>}
          </div>

          <div className={styles.resultsWrap}>
            <ResultsTable result={result} />
          </div>
        </section>
      </div>
    </>
  )
}
