import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import SiteHeader from '../../components/SiteHeader'
import DropZone   from './DropZone'
import QueueView  from './QueueView'
import DemoHistory from './DemoHistory'
import { useUploadQueue } from '../../hooks/useUploadQueue'
import styles from './Upload.module.css'

// view states
const VIEW = { IDLE: 'idle', SINGLE: 'single', QUEUE: 'queue' }

export default function Upload() {
  const navigate      = useNavigate()
  const queryClient   = useQueryClient()
  const [view, setView]     = useState(VIEW.IDLE)
  const [error, setError]   = useState(null)
  const [singleLabel, setSingleLabel] = useState('')
  const [singlePct,   setSinglePct]   = useState(0)
  const { items, summary, start, reset } = useUploadQueue()

  function handleFiles(files, err) {
    setError(null)
    if (err) { setError(err); return }
    if (!files.length) return

    if (files.length === 1) {
      uploadSingle(files[0])
    } else {
      setView(VIEW.QUEUE)
      start(files).then(() => {
        queryClient.invalidateQueries({ queryKey: ['demos'] })
      })
    }
  }

  function uploadSingle(file) {
    setView(VIEW.SINGLE)
    setSingleLabel(`Parsing ${file.name} — this may take a moment…`)
    setSinglePct(0)

    const fd  = new FormData()
    fd.append('demo', file)
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/parse')

    xhr.upload.addEventListener('progress', e => {
      if (e.lengthComputable) {
        const pct = Math.round(e.loaded / e.total * 100)
        setSinglePct(pct)
        setSingleLabel(`Uploading… ${pct}%`)
      }
    })

    xhr.onload = () => {
      if (xhr.status === 200) {
        setSingleLabel('Parsing complete — loading viewer…')
        const data = JSON.parse(xhr.responseText)
        // Navigate by demo ID — no sessionStorage needed
        navigate(`/viewer/${data.session_id}`)
      } else {
        let msg = 'Server error'
        try { msg = JSON.parse(xhr.responseText).error || msg } catch {}
        setView(VIEW.IDLE)
        setError(msg)
      }
    }
    xhr.onerror = () => {
      setView(VIEW.IDLE)
      setError('Network error — is the server running?')
    }
    xhr.send(fd)
  }

  function resetToIdle() {
    reset()
    setView(VIEW.IDLE)
    setError(null)
  }

  return (
    <>
      <SiteHeader>
        <Link to="/admin" className="btn btn-ghost" style={{ marginLeft: 'auto' }}>
          SQL-Admin
        </Link>
      </SiteHeader>

      <main className={styles.main}>
        {view === VIEW.IDLE && (
          <DropZone onFiles={handleFiles} />
        )}

        {view === VIEW.SINGLE && (
          <div className={styles.progressWrap}>
            <p>{singleLabel}</p>
            <div className="progress-bar-bg">
              <div
                className="progress-bar-fill"
                style={{
                  width:     singlePct + '%',
                  animation: singlePct > 0 ? 'none' : undefined,
                }}
              />
            </div>
          </div>
        )}

        {view === VIEW.QUEUE && (
          <QueueView
            items={items}
            summary={summary}
            onUploadMore={resetToIdle}
          />
        )}

        {error && (
          <div className={styles.errorBanner}>⚠ {error}</div>
        )}

        {view === VIEW.IDLE && <DemoHistory />}
      </main>
    </>
  )
}
