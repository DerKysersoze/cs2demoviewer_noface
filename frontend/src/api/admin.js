export const adminApi = {
  schema: () =>
    fetch('/api/admin/schema').then(res => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return res.json()
    }),

  query: (sql) =>
    fetch('/api/admin/query', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ query: sql }),
    }).then(res => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return res.json()
    }),
}
