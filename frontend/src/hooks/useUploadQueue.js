import { useState, useCallback } from 'react'

// Item states: 'queued' | 'uploading' | 'done' | 'error'
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

  function uploadOne(file, idx) {
    return new Promise(resolve => {
      updateItem(idx, { state: 'uploading', progress: 0 })

      const fd  = new FormData()
      fd.append('demo', file)
      const xhr = new XMLHttpRequest()
      xhr.open('POST', '/api/parse')

      xhr.upload.addEventListener('progress', e => {
        if (e.lengthComputable) {
          updateItem(idx, { progress: Math.round(e.loaded / e.total * 100) })
        }
      })

      xhr.onload = () => {
        if (xhr.status === 200) {
          updateItem(idx, { state: 'done', progress: 100 })
          resolve('done')
        } else {
          let msg = 'Server error'
          try { msg = JSON.parse(xhr.responseText).error || msg } catch {}
          updateItem(idx, { state: 'error', error: msg })
          resolve('error')
        }
      }
      xhr.onerror = () => {
        updateItem(idx, { state: 'error', error: 'Network error' })
        resolve('error')
      }
      xhr.send(fd)
    })
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
