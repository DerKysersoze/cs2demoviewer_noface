import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import SiteHeader   from '../../components/SiteHeader'
import LinkButton   from '../../components/ui/LinkButton'
import DotText      from '../../components/ui/DotText'
import MicroLabel   from '../../components/ui/MicroLabel'
import { demosApi } from '../../api/demos'
import { ticksApi } from '../../api/ticks'
import MapReplayStage from '../../components/MapReplayStage'
import { PLAYER_COLORS } from '../../components/playerColors'
import styles from './MapPage.module.css'

function formatTime(secs) {
  if (!isFinite(secs) || secs < 0) return '0:00'
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

// ── Per-player row in the left panel ────────────────────────────
// Health + live weapon (from the current frame) + K/A/D · DMG · HS% + armor.
function PlayerRow({ name, hp, armor, helmet, alive, weapon, color, hasFrames,
                     hidden, onToggle, kills, assists, deaths, dmg, hsPct }) {
  const dead  = hasFrames && (!alive || hp === 0)
  const hpVal = dead ? 0 : hp

  return (
    <div
      className={[styles.replayPlayerRow, hidden ? styles.playerRowHidden : ''].join(' ')}
      onClick={onToggle}
      title={hidden ? `${name} — hidden (click to show)` : `${name} — click to hide`}
    >
      <div className={styles.replayPlayerTop}>
        <span className={`${styles.replayHp}${dead ? ' ' + styles.playerDead : ''}`}>
          {hasFrames ? hpVal : '—'}
        </span>
        <span className={styles.playerDot} style={{ background: color }} />
        <span className={`${styles.replayName}${dead ? ' ' + styles.playerDead : ''}`}>{name}</span>
      </div>

      <div className={styles.weaponRow}>
        <span className={styles.weaponIcon} aria-hidden="true">🔫</span>
        {weapon
          ? <span className={styles.weaponName} title={weapon}>{weapon}</span>
          : <span className={`${styles.weaponName} ${styles.weaponNameUnknown}`} title="Weapon not tracked this frame">—</span>}
      </div>

      <div className={styles.barTrack}>
        <div className={styles.barFill} style={{
          width:      hasFrames ? `${hpVal}%` : '60%',
          background: dead ? '#334155' : color,
          opacity:    dead ? 0.3 : 1,
        }} />
      </div>

      <div className={styles.replayPlayerBot}>
        <span className={styles.replayStats}>
          <span className={styles.statVal}>{kills}/{assists}/{deaths}</span>
          <span className={styles.statSep}>·</span>
          <span>{(dmg ?? 0).toLocaleString()}</span>
          <span className={styles.statSep}>·</span>
          <span>{Math.round(hsPct ?? 0)}%</span>
        </span>
        <span className={styles.replayArmor}>
          {hasFrames && armor > 0 && '🦺'}{hasFrames && helmet && '🪖'}
        </span>
      </div>
    </div>
  )
}

function PlayerPanel({ frames, frame, scoreboard, playerColorMap, hiddenPlayers, togglePlayer, selectedRound, elapsed }) {
  const hasFrames = frames.length > 0
  const current   = frames[frame]

  const stateMap = {}
  current?.p.forEach(pl => {
    stateMap[pl.n] = {
      hp: pl.hp ?? 0, alive: pl.alive,
      armor: pl.armor ?? 0, helmet: pl.helmet ?? false,
      weapon: pl.w ?? null,
    }
  })

  const ct = scoreboard.filter(p => p.team?.toUpperCase().includes('CT'))
  const t  = scoreboard.filter(p => !p.team?.toUpperCase().includes('CT'))

  const renderTeam = (players) => players.map(p => {
    const s = stateMap[p.name] ?? { hp: 100, alive: true, armor: 0, helmet: false, weapon: null }
    return (
      <PlayerRow
        key={p.name}
        name={p.name}
        hp={s.hp}
        armor={s.armor}
        helmet={s.helmet}
        alive={s.alive}
        weapon={s.weapon}
        color={playerColorMap[p.name] || '#fff'}
        hasFrames={hasFrames}
        hidden={hiddenPlayers.has(p.name)}
        onToggle={() => togglePlayer(p.name)}
        kills={p.kills ?? 0}
        assists={p.assists ?? 0}
        deaths={p.deaths ?? 0}
        dmg={p.dmg ?? 0}
        hsPct={p.hs_pct ?? 0}
      />
    )
  })

  return (
    <div className={styles.replayLeftPanel}>
      <div className={styles.replayTeamHeader} style={{ color: 'rgb(var(--t))', borderBottomColor: 'rgb(var(--t))' }}>
        Terrorists
      </div>
      {renderTeam(t)}

      <div className={styles.replayTeamHeader} style={{ color: 'rgb(var(--ct))', borderBottomColor: 'rgb(var(--ct))', marginTop: 10 }}>
        Counter-Terrorists
      </div>
      {renderTeam(ct)}

      <div className={styles.replayPanelFooter}>
        <span className={styles.replayRoundLabel}>
          {selectedRound ? `Round ${selectedRound}` : '—'}
        </span>
        <span className={styles.replayTimer}>
          {hasFrames ? formatTime(elapsed) : '—:——'}
        </span>
      </div>
    </div>
  )
}

const EVENT_CONFIG = {
  kill:   { icon: '💀', cls: 'kill'   },
  hskill: { icon: '🎯', cls: 'hskill' },
  smoke:  { icon: '💨', cls: 'nade'   },
  flash:  { icon: '⚡', cls: 'nade'   },
  he:     { icon: '💥', cls: 'nade'   },
  fire:   { icon: '🔥', cls: 'nade'   },
  buy:    { icon: '🛒', cls: 'buy'    },
  plant:  { icon: '💣', cls: 'plant'  },
  defuse: { icon: '🔵', cls: 'defuse' },
}

function buildEventList(kills, grenades, events, roundNum) {
  const list = []
  kills
    .filter(k => k.round_num === roundNum)
    .forEach(k => {
      list.push({
        tick: k.tick,
        kind: k.headshot ? 'hskill' : 'kill',
        text: k.headshot
          ? `${k.attacker} → ${k.victim} (HS · ${k.weapon})`
          : `${k.attacker} → ${k.victim} (${k.weapon})`,
      })
    })
  grenades.forEach(g => {
    const who  = g.player ? `${g.player}` : 'Unknown'
    const kind = g.type.charAt(0).toUpperCase() + g.type.slice(1)
    list.push({ tick: g.from_tick, kind: g.type, text: `${who} — ${kind}` })
  })
  events.forEach(e => {
    let text = ''
    if (e.type === 'buy')    text = `${e.player} bought ${e.item}`
    if (e.type === 'plant')  text = `${e.player} planted the bomb`
    if (e.type === 'defuse') text = `${e.player} defused the bomb`
    list.push({ tick: e.tick, kind: e.type, text })
  })
  // Buy events always precede live-round action regardless of their recorded tick
  // (CS2 extended buy zone means item_purchase can fire during the first ~5s of live play,
  //  causing buys to sort after early kills if we sort purely by tick)
  return list.sort((a, b) => {
    const aIsBuy = a.kind === 'buy' ? 0 : 1
    const bIsBuy = b.kind === 'buy' ? 0 : 1
    if (aIsBuy !== bIsBuy) return aIsBuy - bIsBuy
    return a.tick - b.tick
  })
}

function EventFeed({ kills, grenades, events, currentTick, roundNum, hasRound, collapsed, onToggle }) {
  const feedRef   = useRef(null)
  const allEvents = useMemo(
    () => buildEventList(kills, grenades, events, roundNum),
    [kills, grenades, events, roundNum]
  )
  const visible = currentTick > 0
    ? allEvents.filter(e => e.tick <= currentTick)
    : allEvents

  useEffect(() => {
    if (!collapsed && feedRef.current)
      feedRef.current.scrollTop = feedRef.current.scrollHeight
  }, [visible.length, collapsed])

  return (
    <div className={[styles.replayFeedPanel, collapsed ? styles.replayFeedCollapsed : ''].join(' ')}>
      <div className={styles.replayFeedHeader} onClick={onToggle} title={collapsed ? 'Expand feed' : 'Collapse feed'}>
        <span className={styles.replayFeedTitle}>Round Feed</span>
        <span className={styles.replayFeedToggle}>{collapsed ? '‹' : '›'}</span>
      </div>
      {!collapsed && (
        <div className={styles.eventFeedBody} ref={feedRef}>
          {!hasRound && <div className={styles.eventFeedEmpty}>Select a round</div>}
          {hasRound && visible.length === 0 && <div className={styles.eventFeedEmpty}>No events yet…</div>}
          {hasRound && visible.map((ev, i) => {
            const cfg = EVENT_CONFIG[ev.kind] || { icon: '•', cls: 'buy' }
            return (
              <div key={i} className={`${styles.eventRow} ${styles['event_' + cfg.cls]}`}>
                <span className={styles.eventIcon}>{cfg.icon}</span>
                <span className={styles.eventText}>{ev.text}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

/**
 * MapPage — the dedicated 2D replay page (replaces the old Viewer "map" tab).
 *
 * Layout: [player details | MapReplayStage | round event feed] + round pills.
 * Player rows show live HP, the weapon held in the current frame, and
 * full-match K/A/D · DMG · HS% from the scoreboard.
 *
 * Deep link: /map/:demoId?round=N jumps straight into that round
 * (used by the "Open fullscreen map" CTA on the Results page's map band).
 */
export default function MapPage() {
  const { demoId } = useParams()
  const [, setSearchParams] = useSearchParams()

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['demo', demoId],
    queryFn:  () => demosApi.get(demoId),
    enabled:  !!demoId,
  })

  const d        = data || null
  const mapName  = d?.header?.map
  const rounds   = useMemo(() => (d?.rounds || []).slice().sort((a, b) => a.round_num - b.round_num), [d])
  const scoreboard = useMemo(() => d?.scoreboard || [], [d])

  const playerColorMap = useMemo(() => {
    const map = {}
    scoreboard.forEach((p, i) => { map[p.name] = PLAYER_COLORS[i % PLAYER_COLORS.length] })
    return map
  }, [scoreboard])

  // Initial round: ?round=N deep link, else first round.
  const [selectedRound, setSelectedRound] = useState(() => {
    const q = new URLSearchParams(window.location.search).get('round')
    return q && !isNaN(parseInt(q)) ? String(parseInt(q)) : ''
  })
  const [hiddenPlayers, setHiddenPlayers] = useState(new Set())
  const [feedCollapsed, setFeedCollapsed] = useState(false)
  const [stageState, setStageState] = useState({ frame: 0, frames: [], playing: false })

  // Resolve the active round once rounds are known: the deep-linked round if
  // it exists, otherwise the first round.
  const activeRound = useMemo(() => {
    if (!rounds.length) return ''
    if (selectedRound && rounds.some(r => String(r.round_num) === selectedRound))
      return selectedRound
    return String(rounds[0].round_num)
  }, [rounds, selectedRound])

  const { data: tickData } = useQuery({
    queryKey: ['ticks', demoId, activeRound],
    queryFn:  () => ticksApi.getRound(demoId, activeRound),
    enabled:  !!activeRound && !!demoId,
    retry:    false,
  })

  const handleStageState = useCallback((s) => setStageState(s), [])

  const togglePlayer = (name) => {
    setHiddenPlayers(prev => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  const selectRound = useCallback((num) => {
    const s = String(num)
    setSelectedRound(s)
    // keep the URL shareable
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      next.set('round', s)
      return next
    }, { replace: true })
  }, [setSearchParams])

  const frames  = stageState.frames
  const frame   = stageState.frame
  const elapsed = (frames.length && frames[frame]?.t != null && frames[0]?.t != null)
    ? (frames[frame].t - frames[0].t) / (d?.header?.tickrate || 128)
    : 0

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
        <div className={styles.center}><MicroLabel>LOADING MAP REPLAY…</MicroLabel></div>
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
        <div className={styles.matchBand}>
          <span className={`${styles.teamName} ${styles.ctColor}`}>{d.ct_team}</span>
          <span className={`${styles.teamScore} ${styles.ctColor}`}>{d.ct_wins}</span>
          <span className={styles.scoreSep}>:</span>
          <span className={`${styles.teamScore} ${styles.tColor}`}>{d.t_wins}</span>
          <span className={`${styles.teamName} ${styles.tColor}`}>{d.t_team}</span>
          <span className={styles.mapPill}><strong>Map:</strong> {mapName}</span>
          <span className={styles.mapPill}><strong>Rounds:</strong> {d.total_rounds}</span>
        </div>

        {!d.has_ticks && (
          <div className={styles.mapPill} style={{ width: '100%', textAlign: 'center', marginBottom: 12 }}>
            Position data not available in this demo — player panels will be inactive.
          </div>
        )}

        <div className={styles.replayWrapper}>
          <div className={styles.replayLayout}>
            <PlayerPanel
              frames={frames}
              frame={frame}
              scoreboard={scoreboard}
              playerColorMap={playerColorMap}
              hiddenPlayers={hiddenPlayers}
              togglePlayer={togglePlayer}
              selectedRound={activeRound}
              elapsed={elapsed}
            />

            <MapReplayStage
              tickData={tickData}
              mapName={mapName}
              kills={d.kills || []}
              roundNum={activeRound ? parseInt(activeRound) : null}
              hasTicks={!!d.has_ticks}
              playerColorMap={playerColorMap}
              hiddenPlayers={hiddenPlayers}
              variant="inline"
              onState={handleStageState}
            />

            <EventFeed
              kills={d.kills || []}
              grenades={tickData?.grenades || []}
              events={tickData?.events || []}
              currentTick={frames[frame]?.t ?? 0}
              roundNum={activeRound ? parseInt(activeRound) : null}
              hasRound={!!activeRound}
              collapsed={feedCollapsed}
              onToggle={() => setFeedCollapsed(c => !c)}
            />
          </div>

          <div className={styles.replayBottomBar}>
            <div className={styles.replayRoundPills}>
              {rounds.map(r => (
                <button
                  key={r.round_num}
                  className={[
                    styles.replayRoundPill,
                    String(r.round_num) === activeRound ? styles.replayRoundPillActive : '',
                  ].join(' ')}
                  onClick={() => selectRound(r.round_num)}
                  disabled={!d.has_ticks}
                  title={`Round ${r.round_num} — ${r.reason}`}
                >
                  {r.round_num}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
