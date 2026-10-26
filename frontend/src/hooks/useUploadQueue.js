import { useState, useCallback } from 'react'
import { demosApi } from '../api/demos'

// Item states: 'queued' | 'uploading' | 'parsing' | 'done' | 'error'
function makeItem(file, idx) {
  return { idx, name: file.name, state: 'queued', progress: 0, error: null }
}

/**
 * Manages sequential multi-file upload with per-item XHR progress.
 *
 * Returns { items, summary, start, reset }
 *   start(files) — kicks off the queue
 *   reset()      — returns to idle
 */
export function useUploadQueue() {
  const [items,   setItems]   = useState([])
  const [summary, setSummary] = useState(null)   // null while running; {done,errors} when complete

  function updateItem(idx, patch) {
    setItems(prev => prev.map(it => it.idx === idx ? { ...it, ...patch } : it))
  }

  async function uploadOne(file, idx) {
    updateItem(idx, { state: 'uploading', progress: 0 })

    const fd = new FormData()
    fd.append('demo', file)
    try {
      // Resolves once the server's background parse job finishes.
      await demosApi.parse(fd, {
        onProgress: (pct) => updateItem(idx, { progress: pct }),
        onPhase: (phase) => {
          if (phase === 'parsing') updateItem(idx, { state: 'parsing', progress: 100 })
        },
      })
      updateItem(idx, { state: 'done', progress: 100 })
      return 'done'
    } catch (e) {
      updateItem(idx, { state: 'error', error: e.message || 'Upload failed' })
      return 'error'
    }
  }

  const start = useCallback(async (files) => {
    const initial = files.map((f, i) => makeItem(f, i))
    setItems(initial)
    setSummary(null)

    let done = 0, errors = 0
    for (let i = 0; i < files.length; i++) {
      const result = await uploadOne(files[i], i)
      result === 'done' ? done++ : errors++
    }
    setSummary({ done, errors, total: files.length })
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  const reset = useCallback(() => {
    setItems([])
    setSummary(null)
  }, [])

  return { items, summary, start, reset }
}
