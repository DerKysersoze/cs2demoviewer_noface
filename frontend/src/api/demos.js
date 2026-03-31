const BASE = '/api'

async function handleResponse(res) {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(text || `HTTP ${res.status}`)
  }
  return res.json()
}

export const demosApi = {
  list:   ()     => fetch(`${BASE}/demos`).then(handleResponse),
  get:    (id)   => fetch(`${BASE}/demos/${id}`).then(handleResponse),
  getLoadout: (id) => fetch(`${BASE}/demos/${id}/loadout`).then(handleResponse),
  delete: (id)   => fetch(`${BASE}/demos/${id}`, { method: 'DELETE' }).then(handleResponse),
  parse:  (formData, onProgress) => new Promise((resolve, reject) => {
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
        xhr.status < 400 ? resolve(data) : reject(new Error(data.error || `HTTP ${xhr.status}`))
      } catch { reject(new Error('Invalid response')) }
    }
    xhr.onerror = () => reject(new Error('Network error'))
    xhr.send(formData)
  }),
}
