import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { demosApi } from '../../api/demos'
import SiteHeader    from '../../components/SiteHeader'
import Scoreboard    from './tabs/Scoreboard'
import Timeline      from './tabs/Timeline'
import Rounds        from './tabs/Rounds'
import KillFeed      from './tabs/KillFeed'
import AimBreakdown  from './tabs/AimBreakdown'
import SwagBreakdown from './tabs/SwagBreakdown'
import MapView       from './tabs/MapView'
import styles from './Viewer.module.css'

const TABS = [
  { id: 'scoreboard', label: 'Scoreboard' },
  { id: 'timeline',   label: 'Timeline' },
  { id: 'map',        label: 'Visual Timeline' },
  { id: 'rounds',     label: 'Rounds' },
  { id: 'killfeed',   label: 'Kill Feed' },
  { id: 'aim',        label: 'Aim Breakdown' },
]

export default function Viewer() {
  const { id }    = useParams()
  const [tab, setTab] = useState('scoreboard')

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['demo', id],
    queryFn:  () => demosApi.get(id),
    enabled:  !!id,
  })

  if (isLoading) return (
    <>
      <SiteHeader><Link to="/" className="btn btn-ghost" style={{ marginLeft: 'auto' }}>← Load another demo</Link></SiteHeader>
      <div className={styles.results}><p className="muted">Loading demo…</p></div>
    </>
  )

  if (isError) return (
    <>
      <SiteHeader><Link to="/" className="btn btn-ghost" style={{ marginLeft: 'auto' }}>← Load another demo</Link></SiteHeader>
      <div className={styles.results}><p style={{ color: 'var(--red)' }}>Failed to load demo: {error?.message}</p></div>
    </>
  )

  const d = data
  const h = d.header || {}

  return (
    <>
      <SiteHeader>
        <Link to="/" className="btn btn-ghost" style={{ marginLeft: 'auto' }}>
          ← Load another demo
        </Link>
      </SiteHeader>

      <div className={styles.results}>
        {/* Match header */}
        <div className={styles.matchHeader}>
          <div className={styles.matchScore}>
            <div className={styles.teamBlock}>
              <div className={`${styles.teamName} ${styles.ctColor}`}>{d.ct_team}</div>
              <div className={`${styles.teamScore} ${styles.ctColor}`}>{d.ct_wins}</div>
            </div>
            <div className={styles.scoreSep}>:</div>
            <div className={styles.teamBlock}>
              <div className={`${styles.teamName} ${styles.tColor}`}>{d.t_team}</div>
              <div className={`${styles.teamScore} ${styles.tColor}`}>{d.t_wins}</div>
            </div>
          </div>
          <div className={styles.metaPills}>
            {[
              ['File',      d.filename],
              ['Map',       h.map],
              ['Tickrate',  h.tickrate ? `${h.tickrate} Hz` : '—'],
              ['Duration',  h.duration],
              ['Rounds',    d.total_rounds],
            ].map(([k, v]) => (
              <div key={k} className={styles.pill}>
                <strong>{k}:</strong> {v}
              </div>
            ))}
          </div>
        </div>

        {/* Tab bar */}
        <div className={styles.tabs}>
          {TABS.map(t => (
            <button
              key={t.id}
              className={`${styles.tabBtn}${tab === t.id ? ' ' + styles.active : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Tab panels */}
        {tab === 'scoreboard' && <Scoreboard scoreboard={d.scoreboard || []} />}
        {tab === 'timeline'   && <Timeline   rounds={d.rounds || []} kills={d.kills || []} ctTeam={d.ct_team} tTeam={d.t_team} />}
        {tab === 'map'        && <MapView demo={d} demoId={id} />}
        {tab === 'rounds'     && <Rounds     rounds={d.rounds || []} />}
        {tab === 'killfeed'   && <KillFeed   kills={d.kills || []} />}
        {tab === 'aim'        && <AimBreakdown  aimBreakdown={d.aim_breakdown || []} />}
      </div>
    </>
  )
}
