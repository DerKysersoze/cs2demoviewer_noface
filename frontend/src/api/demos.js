const BASE = '/api'

async function handleResponse(res) {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(text || `HTTP ${res.status}`)
  }
  return res.json()
}

// The server parses in a background job (~30–60 s).  Poll the job until it
// finishes and resolve with the full parse payload (same shape as the old
// synchronous /api/parse response).
function pollJob(jobId, { intervalMs = 1200, timeoutMs = 300000 } = {}) {
  return new Promise((resolve, reject) => {
    const t0 = Date.now()
    const tick = async () => {
      try {
        const res = await fetch(`${BASE}/jobs/${jobId}`)
        const body = res.ok ? await res.json() : { error: `HTTP ${res.status}` }
        if (body.status === 'done') return resolve(body.data)
        if (body.status === 'error') return reject(new Error(body.error || 'Parse failed'))
        if (Date.now() - t0 > timeoutMs) return reject(new Error('Parsing timed out — please try again'))
        setTimeout(tick, intervalMs)
      } catch (e) {
        reject(e)
      }
    }
    tick()
  })
}

export const demosApi = {
  list:   ()     => fetch(`${BASE}/demos`).then(handleResponse),
  get:    (id)   => fetch(`${BASE}/demos/${id}`).then(handleResponse),
  getLoadout: (id) => fetch(`${BASE}/demos/${id}/loadout`).then(handleResponse),
  delete: (id)   => fetch(`${BASE}/demos/${id}`, { method: 'DELETE' }).then(handleResponse),
  // Upload + parse.  Resolves with the full parse payload once the server's
  // background parse job completes.
  //   options.onProgress(pct)  — upload progress 0–100
  //   options.onPhase(phase)   — called with 'parsing' once upload finished
  parse:  (formData, { onProgress, onPhase } = {}) => new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${BASE}/parse`)
    if (onProgress) {
      xhr.upload.addEventListener('progress', e => {
        if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100))
      })
    }
    xhr.onload  = () => {
      try {
        const data = JSON.parse(xhr.responseText)
        if (xhr.status >= 400) return reject(new Error(data.error || `HTTP ${xhr.status}`))
        if (data.job_id) {
          if (onPhase) onPhase('parsing')
          return pollJob(data.job_id).then(resolve, reject)
        }
        resolve(data)  // compatibility with a synchronous response
      } catch { reject(new Error('Invalid response')) }
    }
    xhr.onerror = () => reject(new Error('Network error'))
    xhr.send(formData)
  }),
}
