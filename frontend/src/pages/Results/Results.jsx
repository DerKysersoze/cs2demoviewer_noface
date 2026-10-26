import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import SiteHeader from '../../components/SiteHeader'
import DotText from '../../components/ui/DotText'
import MicroLabel from '../../components/ui/MicroLabel'
import LinkButton from '../../components/ui/LinkButton'
import { demosApi } from '../../api/demos'
import MatchHeader from './MatchHeader'
import MatchStats from './MatchStats'
import RoundChips from './RoundChips'
import RoundStory from './RoundStory'
import RoundMap from './RoundMap'
import Highlights from './Highlights'
import deriveHighlights from './deriveHighlights'
import AimBreakdown from '../Aim/AimBreakdown'
import PlayerDossier from './PlayerDossier'
import styles from './Results.module.css'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'rounds',   label: 'Rounds' },
  { id: 'aim',      label: 'Aim' },
  { id: 'players',  label: 'Players' },
]

/**
 * Results — the match results page, organised as four tabs under the match
 * header band:
 *
 *   OVERVIEW — full-match stats table + highlights (jump switches to Rounds)
 *   ROUNDS   — round chips, then the 2D map companion as main content
 *              (~80% right, always visible) with the kill-feed story as a
 *              compact rail on the left (~20%)
 *   AIM      — shared AimBreakdown (player list + summary, hit bars, weapons)
 *   PLAYERS  — PlayerDossier: CT/T rail; per player, match + aim stats, hit
 *              location and per-weapon table all in one place
 *
 * Loading and "match not found" states, ←/→ keyboard round navigation and
 * delete → home are unchanged.
 */
export default function Results() {
  const { demoId } = useParams()
  const navigate = useNavigate()
  const [selected, setSelected] = useState(1)
  const [tab, setTab] = useState('overview')

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['demo', demoId],
    queryFn:  () => demosApi.get(demoId),
    enabled:  !!demoId,
  })

  const d = data || null
  const rounds = useMemo(
    () => (d?.rounds || []).slice().sort((a, b) => a.round_num - b.round_num),
    [d]
  )
  // name -> SteamID64, from the scoreboard (the only table with ids) — used
  // to link kill-feed names to their Steam community profiles.
  const sidByPlayer = useMemo(() => {
    const m = {}
    for (const p of d?.scoreboard || []) if (p.name && p.steamid) m[p.name] = p.steamid
    return m
  }, [d])
  const tickrate = parseInt(d?.header?.tickrate, 10) || 128
  const highlights = useMemo(
    () =>
      deriveHighlights({
        rounds: d?.rounds || [],
        kills: d?.kills || [],
        scoreboard: d?.scoreboard || [],
        tickrate,
      }),
    [d, tickrate]
  )

  // Resolve the active round once the payload is known (or for odd round
  // sets): the user's pick if still valid, otherwise the first round.
  const activeSelected = rounds.length
    ? (rounds.some((r) => r.round_num === selected) ? selected : rounds[0].round_num)
    : selected

  // Keyboard round navigation (← / →)
  useEffect(() => {
    if (!rounds.length) return undefined
    function onKey(e) {
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return
      const delta = e.key === 'ArrowLeft' ? -1 : 1
      setSelected((s) => {
        const base = rounds.some((r) => r.round_num === s) ? s : rounds[0].round_num
        return base + delta
      })
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [rounds])

  const handleDelete = useCallback(async () => {
    if (!window.confirm('Delete this demo and its stored file? This cannot be undone.')) return
    await demosApi.delete(demoId)
    navigate('/')
  }, [demoId, navigate])

  // Highlights (and any future jump source) select the round AND switch to
  // the Rounds tab so the user lands on the story.
  const jumpToRound = useCallback((roundNum) => {
    setSelected(roundNum)
    setTab('rounds')
  }, [])

  const header = (
    <SiteHeader>
      <Link to="/" className="btn btn-ghost">← Home</Link>
    </SiteHeader>
  )

  if (isLoading) {
    return (
      <>
        {header}
        <div className={styles.center}>
          <MicroLabel className={styles.metaLine}>LOADING MATCH…</MicroLabel>
        </div>
      </>
    )
  }

  if (isError || !d || rounds.length === 0) {
    return (
      <>
        {header}
        <div className={styles.center}>
          <DotText className={styles.notFoundTitle}>match not found</DotText>
          <p className={styles.metaLine}>
            {isError
              ? error?.message || 'It may have been deleted.'
              : 'No rounds were parsed for this demo.'}
          </p>
          <Link to="/" className="link-underline" style={{ marginTop: 16 }}>
            BACK TO HOME
          </Link>
        </div>
      </>
    )
  }

  const current = rounds.find((r) => r.round_num === activeSelected) || rounds[0]

  return (
    <>
      {header}

      <div className={styles.page}>
        <MatchHeader d={d} />

        <nav className={styles.tabbar} aria-label="Match sections">
          <div className={styles.tablist} role="tablist">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={tab === t.id}
                className={`${styles.tab}${tab === t.id ? ' ' + styles.tabOn : ''}`}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>
          <LinkButton to={`/loadout/${demoId}`} className={styles.tabCta}>
            Loadout
          </LinkButton>
        </nav>

        {tab === 'overview' && (
          <div role="tabpanel" aria-label="Overview">
            <div className={styles.section}>
              <MicroLabel className={styles.sectionLabel}>FULL MATCH STATS</MicroLabel>
              <MatchStats scoreboard={d.scoreboard || []} />
            </div>

            <div className={styles.section}>
              <Highlights highlights={highlights} onJump={jumpToRound} />
            </div>
          </div>
        )}

        {tab === 'rounds' && (
          <div role="tabpanel" aria-label="Rounds">
            <div className={styles.section}>
              <RoundChips rounds={rounds} selected={activeSelected} onSelect={setSelected} />
            </div>

            {d.has_ticks && d.header?.map ? (
              <div className={styles.roundsSplit}>
                <RoundStory
                  round={current}
                  kills={d.kills || []}
                  tickrate={tickrate}
                  players={sidByPlayer}
                />
                <RoundMap
                  demoId={demoId}
                  mapName={d.header.map}
                  roundNum={current.round_num}
                  kills={d.kills || []}
                  scoreboard={d.scoreboard || []}
                />
              </div>
            ) : (
              <div className={styles.section}>
                <RoundStory
                  round={current}
                  kills={d.kills || []}
                  tickrate={tickrate}
                  players={sidByPlayer}
                />
              </div>
            )}
          </div>
        )}

        {tab === 'aim' && (
          <div role="tabpanel" aria-label="Aim">
            <div className={styles.section}>
              <MicroLabel className={styles.sectionLabel}>AIM BREAKDOWN</MicroLabel>
              {d.aim_breakdown?.length ? (
                <AimBreakdown aimBreakdown={d.aim_breakdown} />
              ) : (
                <p className={styles.metaLine}>No aim data in this demo.</p>
              )}
            </div>
          </div>
        )}

        {tab === 'players' && (
          <div role="tabpanel" aria-label="Players">
            <div className={styles.section}>
              <MicroLabel className={styles.sectionLabel}>
                PLAYERS — MATCH + AIM, ONE PLACE
              </MicroLabel>
              <PlayerDossier
                scoreboard={d.scoreboard || []}
                aimBreakdown={d.aim_breakdown || []}
              />
            </div>
          </div>
        )}

        <div className={styles.dangerZone}>
          <button type="button" className="btn btn-danger" onClick={handleDelete}>
            Delete demo
          </button>
        </div>
      </div>
    </>
  )
}
