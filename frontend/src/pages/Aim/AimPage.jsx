import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import SiteHeader   from '../../components/SiteHeader'
import LinkButton   from '../../components/ui/LinkButton'
import DotText      from '../../components/ui/DotText'
import MicroLabel   from '../../components/ui/MicroLabel'
import { demosApi } from '../../api/demos'
import AimBreakdown from './AimBreakdown'
import styles from './AimPage.module.css'

/**
 * AimPage — standalone per-player aim breakdown (kept as a shareable route;
 * the same breakdown also lives inline on the Results page — Aim tab and,
 * per player, the Players tab).
 */
export default function AimPage() {
  const { demoId } = useParams()

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['demo', demoId],
    queryFn:  () => demosApi.get(demoId),
    enabled:  !!demoId,
  })

  const d = data || null
  const header = (
    <SiteHeader>
      <LinkButton to={`/results/${demoId}`}>← Results</LinkButton>
      <Link to="/" className="btn btn-ghost" style={{ marginLeft: 'auto' }}>← Home</Link>
    </SiteHeader>
  )

  if (isLoading) {
    return (
      <>
        {header}
        <div className={styles.center}><MicroLabel>LOADING AIM BREAKDOWN…</MicroLabel></div>
      </>
    )
  }

  if (isError || !d) {
    return (
      <>
        {header}
        <div className={styles.center}>
          <DotText className={styles.notFound}>match not found</DotText>
          <p style={{ color: 'var(--muted)' }}>{error?.message || 'It may have been deleted.'}</p>
          <Link to={`/results/${demoId}`} className="link-underline" style={{ marginTop: 16 }}>BACK TO RESULTS</Link>
        </div>
      </>
    )
  }

  return (
    <>
      {header}
      <div className={styles.page}>
        <div className={styles.titleRow}>
          <span className={styles.title}>Aim Breakdown</span>
          <span className={styles.mapPill}><strong>Map:</strong> {d.header?.map}</span>
          <span className={styles.mapPill}>{d.filename}</span>
        </div>
        <AimBreakdown aimBreakdown={d.aim_breakdown || []} />
      </div>
    </>
  )
}
