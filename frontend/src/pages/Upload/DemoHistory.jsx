import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { demosApi } from '../../api/demos'
import DemoCard from './DemoCard'
import styles from './Upload.module.css'

/**
 * Match library grid (front page, mockup option A): one card per demo with
 * map image, score, winner badge and meta; hover reveals quick stats
 * (top performer, rounds, duration, CTA). Delete lives on each card.
 */
export default function DemoHistory() {
  const queryClient = useQueryClient()

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
      <div className={styles.gridHead}>
        <h2 className={styles.historyHeading}>Match library</h2>
        <span className={styles.count}>
          {demos.length} {demos.length === 1 ? 'match' : 'matches'} · newest first
        </span>
      </div>

      {demos.length === 0 ? (
        <p className={styles.historyEmpty}>No demos saved yet — drop one above.</p>
      ) : (
        <div className={styles.cardGrid}>
          {demos.map(d => (
            <DemoCard key={d.id} demo={d} onDelete={() => deleteMutation.mutate(d.id)} />
          ))}
        </div>
      )}
    </section>
  )
}
