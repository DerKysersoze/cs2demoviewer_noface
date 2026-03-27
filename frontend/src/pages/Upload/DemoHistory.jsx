import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { demosApi } from '../../api/demos'
import styles from './Upload.module.css'

function formatDate(str) {
  const ts = new Date(str)
  if (isNaN(ts)) return str
  return ts.toLocaleString(undefined, {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function DemoHistory() {
  const navigate     = useNavigate()
  const queryClient  = useQueryClient()

  const { data: demos = [], isLoading } = useQuery({
    queryKey: ['demos'],
    queryFn:  demosApi.list,
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => demosApi.delete(id),
    onSuccess:  ()   => queryClient.invalidateQueries({ queryKey: ['demos'] }),
  })

  if (isLoading) return null

  return (
    <section className={styles.historySection}>
      <h2 className={styles.historyHeading}>Previous Demos</h2>

      {demos.length === 0 && (
        <p className={styles.historyEmpty}>No demos saved yet.</p>
      )}

      <div className={styles.historyList}>
        {demos.map(d => (
          <div
            key={d.id}
            className={styles.demoRow}
            onClick={() => navigate(`/viewer/${d.id}`)}
          >
            <div className={styles.demoName} title={d.filename}>{d.filename}</div>
            <div className={styles.demoMeta}>{d.map} &nbsp;·&nbsp; {formatDate(d.uploaded_at)}</div>
            <button
              className={styles.demoDel}
              title="Delete"
              onClick={e => {
                e.stopPropagation()
                deleteMutation.mutate(d.id)
              }}
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </section>
  )
}
