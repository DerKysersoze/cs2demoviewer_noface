import { useState, useEffect, useRef, useCallback, useMemo, memo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ticksApi } from '../../../api/ticks'
import { useMapCanvas } from '../../../hooks/useMapCanvas'
import styles from '../Viewer.module.css'

const PLAYER_COLORS = [
  '#ff6b6b', '#ff9f1c', '#6bcb77', '#c77dff', '#f72585',
  '#e05c00', '#2ec4b6', '#ff4db8', '#80b918', '#adb5bd',
]

// ── Per-player horizontal health bars ─────────────────────────
function PlayerBar({ name, hp, armor, helmet, alive, color, hasFrames, hidden, onToggle }) {
  const dead     = hasFrames && (!alive || hp === 0)
  const hpPct    = dead ? 0 : hp
  const armorPct = dead ? 0 : (armor ?? 0)
  const armorColor = helmet ? '#94a3b8' : '#64748b'

  return (
    <div
      className={[styles.playerRow, styles.playerRowClickable, hidden ? styles.playerRowHidden : ''].join(' ')}
      onClick={onToggle}
      title={hidden ? `${name} — hidden (click to show)` : `${name} — click to hide`}
    >
      {/* Name + HP */}
      <div className={styles.playerRowTop}>
        <span className={styles.playerDot} style={{ background: color }} />
        <span className={`${styles.playerName}${dead ? ' ' + styles.playerDead : ''}`}>{name}</span>
        <span className={`${styles.playerHp}${dead ? ' ' + styles.playerDead : ''}`}>
          {hasFrames ? (dead ? 0 : hp) : '—'}
        </span>
      </div>

      {/* HP bar */}
      <div className={styles.barTrack}>
        <div className={styles.barFill} style={{
          width:      hasFrames ? `${hpPct}%` : '60%',
          background: dead ? '#334155' : color,
          opacity:    dead ? 0.3 : 1,
        }} />
      </div>

      {/* Armor row — only when frames are loaded */}
      {hasFrames && (
        <div className={styles.armorRow}>
          <span className={styles.armorIcon} title={helmet ? 'Kevlar + Helmet' : 'Kevlar only'}>
            {armor > 0 && '🦺'}{helmet && '🪖'}
          </span>
          <div className={styles.barTrack} style={{ flex: 1 }}>
            <div className={styles.barFill} style={{
              width:      `${armorPct}%`,
              background: dead ? '#1e293b' : armorColor,
              opacity:    dead ? 0.3 : 1,
            }} />
          </div>
          <span className={styles.armorNum}>{dead ? 0 : (armor ?? 0)}</span>
        </div>
      )}
    </div>
  )
}

function PlayerHealthBars({ frames, frame, scoreboard, playerColorMap, hiddenPlayers, togglePlayer }) {
  const hasFrames = frames.length > 0
  const current   = frames[frame]

  const stateMap = {}
  current?.p.forEach(pl => {
    stateMap[pl.n] = { hp: pl.hp ?? 0, alive: pl.alive, armor: pl.armor ?? 0, helmet: pl.helmet ?? false }
  })

  const ct = scoreboard.filter(p => p.team?.toUpperCase().includes('CT'))
  const t  = scoreboard.filter(p => !p.team?.toUpperCase().includes('CT'))

  const renderTeam = (players) => players.map(p => {
    const s = stateMap[p.name] ?? { hp: 100, alive: true, armor: 0, helmet: false }
    return (
      <PlayerBar
        key={p.name}
        name={p.name}
        hp={s.hp}
        armor={s.armor}
        helmet={s.helmet}
        alive={s.alive}
        color={playerColorMap[p.name] || '#fff'}
        hasFrames={hasFrames}
        hidden={hiddenPlayers.has(p.name)}
        onToggle={() => togglePlayer(p.name)}
      />
    )
  })

  return (
    <div className={styles.healthPanel}>
      {/* V2: panel header with title + hint */}
      <div className={styles.healthPanelHeader}>
        <span className={styles.healthPanelTitle}>Live Status</span>
        {hasFrames && <span className={styles.healthPanelHint}>click to hide</span>}
      </div>
      <div className={styles.healthPanelBody}>
        <div className={styles.teamSectionLabel} style={{ color: 'var(--ct)' }}>CT</div>
        {renderTeam(ct)}
        <div className={styles.teamDivider} />
        <div className={styles.teamSectionLabel} style={{ color: 'var(--t)' }}>T</div>
        {renderTeam(t)}
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

  return list.sort((a, b) => a.tick - b.tick)
}

const EventFeed = memo(function EventFeed({ kills, grenades, events, currentTick, roundNum, hasRound }) {
  const feedRef   = useRef(null)
  const allEvents = useMemo(
    () => buildEventList(kills, grenades, events, roundNum),
    [kills, grenades, events, roundNum]
  )
  const visible = allEvents.filter(e => e.tick <= currentTick)

  useEffect(() => {
    if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight
  }, [visible.length])

  return (
    <div className={styles.eventFeedPanel}>
      <div className={styles.eventFeedHeader}>Round Feed</div>
      <div className={styles.eventFeedBody} ref={feedRef}>
        {!hasRound && (
          <div className={styles.eventFeedEmpty}>Select a round to see events</div>
        )}
        {hasRound && visible.length === 0 && (
          <div className={styles.eventFeedEmpty}>No events yet…</div>
        )}
        {visible.map((ev, i) => {
          const cfg = EVENT_CONFIG[ev.kind] || { icon: '•', cls: 'buy' }
          return (
            <div key={i} className={`${styles.eventRow} ${styles['event_' + cfg.cls]}`}>
              <span className={styles.eventIcon}>{cfg.icon}</span>
              <span className={styles.eventText}>{ev.text}</span>
              <span className={styles.eventTick}>{ev.tick}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
})

export default function MapViewV2({ demo, demoId }) {
  const mapName    = demo.header?.map
  const rounds     = demo.rounds    || []
  const scoreboard = demo.scoreboard || []

  const playerColorMap = useMemo(() => {
    const map = {}
    scoreboard.forEach((p, i) => { map[p.name] = PLAYER_COLORS[i % PLAYER_COLORS.length] })
    return map
  }, [scoreboard])

  const [selectedRound, setSelectedRound] = useState('')
  const [frames,      setFrames]      = useState([])
  const [grenades,    setGrenades]    = useState([])
  const [roundEvents, setRoundEvents] = useState([])
  const [frame,    setFrame]    = useState(0)
  const [playing,  setPlaying]  = useState(false)
  const [speed,    setSpeed]    = useState(1)
  const [bounds,   setBounds]   = useState(null)
  const [hiddenPlayers, setHiddenPlayers] = useState(new Set())
  const [imageVer, setImageVer] = useState(0)
  const [overlay, setOverlay] = useState({
    show: true,
    icon: '🗺',
    msg:  demo.has_ticks
      ? 'Select a round to view player positions'
      : 'Position data not available in this demo',
    showDownload: false,
    downloading:  false,
  })

  const timerRef    = useRef(null)
  const mapImageRef = useRef(null)
  const { canvasRef, redraw } = useMapCanvas()

  const stopPlayback = useCallback(() => {
    clearInterval(timerRef.current)
    setPlaying(false)
  }, [])

  useEffect(() => {
    if (!playing || !frames.length) return
    timerRef.current = setInterval(() => {
      setFrame(prev => {
        if (prev >= frames.length - 1) {
          clearInterval(timerRef.current)
          setPlaying(false)
          return frames.length - 1
        }
        return prev + 1
      })
    }, Math.max(16, Math.round(100 / speed)))
    return () => clearInterval(timerRef.current)
  }, [playing, speed, frames.length])

  const loadMapImage = useCallback((name, bustCache) => {
    const img = new Image()
    img.onload  = () => { mapImageRef.current = img; setImageVer(v => v + 1) }
    img.onerror = () => { mapImageRef.current = null }
    img.src = ticksApi.mapImageUrl(name) + (bustCache ? `?t=${Date.now()}` : '')
  }, [])

  const { data: mapsReadyData } = useQuery({
    queryKey: ['maps_ready'],
    queryFn:  ticksApi.mapsReady,
    retry:    false,
  })
  useEffect(() => {
    if (!mapsReadyData || !mapName) return
    if (mapsReadyData.ready) {
      loadMapImage(mapName, false)
    } else {
      setOverlay(o => ({ ...o, icon: '⬇️', msg: 'Map radar images not downloaded yet.', showDownload: true }))
    }
  }, [mapsReadyData, mapName, loadMapImage])

  const { data: mapInfoData } = useQuery({
    queryKey: ['map_info', mapName],
    queryFn:  () => ticksApi.getMapInfo(mapName),
    enabled:  !!mapName,
  })
  useEffect(() => { if (mapInfoData) setBounds(mapInfoData) }, [mapInfoData])

  const { data: tickData } = useQuery({
    queryKey: ['ticks', demoId, selectedRound],
    queryFn:  () => ticksApi.getRound(demoId, selectedRound),
    enabled:  !!selectedRound && !!demoId,
    retry:    false,
  })
  useEffect(() => {
    if (!tickData) return
    if (tickData.error) {
      setOverlay({ show: true, icon: '❌', msg: tickData.error, showDownload: false, downloading: false })
      setFrames([])
      return
    }
    console.log('tickData keys:', Object.keys(tickData), 'grenades:', tickData.grenades?.length)
    const f = tickData.frames || []
    setFrames(f)
    setGrenades(tickData.grenades || [])
    setRoundEvents(tickData.events || [])
    setFrame(0)
    if (!f.length) {
      setOverlay({ show: true, icon: '❌', msg: 'No position data for this round', showDownload: false, downloading: false })
    } else {
      setOverlay({ show: false, icon: '', msg: '', showDownload: false, downloading: false })
    }
  }, [tickData])

  useEffect(() => {
    redraw(frames, frame, bounds, mapImageRef.current, hiddenPlayers, playerColorMap, grenades)
  }, [frames, frame, bounds, hiddenPlayers, imageVer, playerColorMap, grenades, redraw])

  const handleRoundChange = (e) => {
    const val = e.target.value
    stopPlayback()
    setFrames([])
    setGrenades([])
    setRoundEvents([])
    setFrame(0)
    setOverlay(prev => ({
      ...prev,
      show: true,
      icon: val ? '⏳' : '🗺',
      msg:  val ? 'Loading…'
               : (demo.has_ticks ? 'Select a round to view player positions' : 'Position data not available'),
      showDownload: false,
    }))
    setSelectedRound(val)
  }

  const handleDownload = () => {
    setOverlay(o => ({ ...o, icon: '⏳', msg: 'Downloading map images, please wait…', downloading: true }))
    ticksApi.downloadMaps()
      .then(d => {
        if (d.error) {
          setOverlay(o => ({ ...o, icon: '❌', msg: `Download failed: ${d.error}`, downloading: false }))
        } else {
          setOverlay(o => ({ ...o, icon: '✅', msg: 'Maps downloaded! Select a round to begin.', showDownload: false, downloading: false }))
          if (mapName) loadMapImage(mapName, true)
        }
      })
      .catch(() =>
        setOverlay(o => ({ ...o, icon: '❌', msg: 'Network error during download.', downloading: false }))
      )
  }

  const togglePlayer = (name) => {
    setHiddenPlayers(prev => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  const currentTick    = frames[frame]?.t ?? 0
  const activeGrenades = grenades.filter(g => currentTick >= g.from_tick && currentTick <= g.to_tick)
  const tickLabel      = frames.length
    ? `Frame ${frame + 1} / ${frames.length}  •  Tick ${frames[frame]?.t ?? '—'}`
    : '—'

  return (
    <div className={styles.mapLayoutV2}>

      {/* ── Health bars (left) — V2: toggle-hide on rows, Live Status header ── */}
      <PlayerHealthBars
        frames={frames}
        frame={frame}
        scoreboard={scoreboard}
        playerColorMap={playerColorMap}
        hiddenPlayers={hiddenPlayers}
        togglePlayer={togglePlayer}
      />

      {/* ── Canvas area ── */}
      <div className={styles.mapCanvasWrapV2}>
        <canvas ref={canvasRef} className={styles.mapCanvas} />
        {overlay.show && (
          <div className={styles.mapOverlay}>
            <span className={styles.mapOverlayIcon}>{overlay.icon}</span>
            <span className={styles.mapOverlayMsg}>{overlay.msg}</span>
            {overlay.showDownload && (
              <button className="btn" onClick={handleDownload} disabled={overlay.downloading}>
                {overlay.downloading ? 'Downloading…' : 'Download Map Images (~100 MB)'}
              </button>
            )}
          </div>
        )}
      </div>

      {/* ── Sidebar — V2: controls + event feed ── */}
      <div className={styles.mapSidebar}>
        <div className={styles.mapControls}>
          <label className={styles.mapLabel}>Round</label>
          <select
            className={styles.mapSelect}
            value={selectedRound}
            onChange={handleRoundChange}
            disabled={!demo.has_ticks}
          >
            <option value="">— select —</option>
            {rounds.map(r => (
              <option key={r.round_num} value={r.round_num}>
                Round {r.round_num} — {r.reason}
              </option>
            ))}
          </select>

          <label className={styles.mapLabel} style={{ marginTop: 8 }}>Playback</label>
          <div className={styles.mapPlayback}>
            <button
              className="btn"
              style={playing ? { background: 'var(--ct)', color: '#fff', borderColor: 'var(--ct)' } : {}}
              onClick={() => { if (!frames.length) return; playing ? stopPlayback() : setPlaying(true) }}
              disabled={!frames.length}
            >
              {playing ? '⏸ Pause' : '▶ Play'}
            </button>
            <select
              className={styles.mapSelect}
              style={{ flex: 1 }}
              value={speed}
              onChange={e => {
                const s = parseFloat(e.target.value)
                setSpeed(s)
                if (playing) { stopPlayback(); setPlaying(true) }
              }}
            >
              <option value="0.5">0.5×</option>
              <option value="1">1×</option>
              <option value="2">2×</option>
              <option value="4">4×</option>
            </select>
          </div>

          <input
            type="range"
            className={styles.mapScrubber}
            min={0}
            max={Math.max(0, frames.length - 1)}
            value={frame}
            onChange={e => { stopPlayback(); setFrame(parseInt(e.target.value)) }}
            disabled={!frames.length}
          />
          <div className={styles.mapTickLabel}>{tickLabel}</div>
          {grenades.length > 0 && (
            <div className={styles.mapTickLabel} style={{ color: activeGrenades.length ? '#fbbf24' : 'var(--muted)' }}>
              Nades: {grenades.length} total • {activeGrenades.length} active
            </div>
          )}
        </div>

        <EventFeed
          kills={demo.kills || []}
          grenades={grenades}
          events={roundEvents}
          currentTick={currentTick}
          roundNum={selectedRound ? parseInt(selectedRound) : null}
          hasRound={!!selectedRound}
        />

      </div>

    </div>
  )
}
