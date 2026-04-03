import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ticksApi } from '../../../api/ticks'
import { useMapCanvas } from '../../../hooks/useMapCanvas'
import styles from '../Viewer.module.css'

const PLAYER_COLORS = [
  '#ff6b6b', '#ff9f1c', '#6bcb77', '#c77dff', '#f72585',
  '#e05c00', '#2ec4b6', '#ff4db8', '#80b918', '#adb5bd',
]

function formatTime(secs) {
  if (!isFinite(secs) || secs < 0) return '0:00'
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

// ── Per-player row in the left panel ────────────────────────────
function PlayerRow({ name, hp, armor, helmet, alive, color, hasFrames, hidden, onToggle, kills, assists, deaths }) {
  const dead = hasFrames && (!alive || hp === 0)
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
      <div className={styles.barTrack}>
        <div className={styles.barFill} style={{
          width:      hasFrames ? `${hpVal}%` : '60%',
          background: dead ? '#334155' : color,
          opacity:    dead ? 0.3 : 1,
        }} />
      </div>
      <div className={styles.replayPlayerBot}>
        <span className={styles.replayKad}>{kills}/{assists}/{deaths}</span>
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
    stateMap[pl.n] = { hp: pl.hp ?? 0, alive: pl.alive, armor: pl.armor ?? 0, helmet: pl.helmet ?? false }
  })

  const ct = scoreboard.filter(p => p.team?.toUpperCase().includes('CT'))
  const t  = scoreboard.filter(p => !p.team?.toUpperCase().includes('CT'))

  const renderTeam = (players) => players.map(p => {
    const s = stateMap[p.name] ?? { hp: 100, alive: true, armor: 0, helmet: false }
    return (
      <PlayerRow
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
        kills={p.kills ?? 0}
        assists={p.assists ?? 0}
        deaths={p.deaths ?? 0}
      />
    )
  })

  return (
    <div className={styles.replayLeftPanel}>
      <div className={styles.replayTeamHeader} style={{ color: 'var(--t)', borderBottomColor: 'var(--t)' }}>
        Terrorists
      </div>
      {renderTeam(t)}

      <div className={styles.replayTeamHeader} style={{ color: 'var(--ct)', borderBottomColor: 'var(--ct)', marginTop: 10 }}>
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

// ── Timeline scrubber with kill + bomb markers ───────────────────
function TimelineScrubber({ frames, frame, kills, roundEvents, selectedRound, onScrub, disabled }) {
  const startTick = frames[0]?.t ?? 0
  const endTick   = frames[frames.length - 1]?.t ?? 1
  const range     = endTick - startTick || 1

  const killMarkers = useMemo(() => {
    if (!frames.length || !selectedRound) return []
    const roundNum = parseInt(selectedRound)
    return kills
      .filter(k => k.round_num === roundNum && k.tick >= startTick && k.tick <= endTick)
      .map(k => ({ pct: (k.tick - startTick) / range * 100, hs: k.headshot }))
  }, [kills, selectedRound, startTick, endTick, range, frames.length])

  const bombRegion = useMemo(() => {
    if (!frames.length) return null
    const plantEvt  = roundEvents.find(e => e.type === 'plant')
    const resolveEvt = roundEvents.find(e => e.type === 'defuse' || e.type === 'explode')
    if (!plantEvt) return null
    const endT = resolveEvt ? resolveEvt.tick : endTick
    return {
      left:  Math.max(0, (plantEvt.tick - startTick) / range * 100),
      width: Math.min(100, (endT - plantEvt.tick) / range * 100),
    }
  }, [roundEvents, startTick, endTick, range, frames.length])

  return (
    <div className={styles.replayTimeline}>
      {bombRegion && (
        <div
          className={styles.scrubberBombRegion}
          style={{ left: `${bombRegion.left}%`, width: `${bombRegion.width}%` }}
        />
      )}
      {killMarkers.map((m, i) => (
        <div
          key={i}
          className={styles.scrubberMarker}
          style={{ left: `${m.pct}%`, background: m.hs ? '#facc15' : 'var(--red)' }}
        />
      ))}
      <input
        type="range"
        className={styles.mapScrubber}
        style={{ position: 'relative', zIndex: 1, width: '100%', margin: 0 }}
        min={0}
        max={Math.max(0, frames.length - 1)}
        value={frame}
        onChange={e => onScrub(parseInt(e.target.value))}
        disabled={disabled}
      />
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
          {visible.map((ev, i) => {
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
  const [shots,       setShots]       = useState([])
  const [frame,    setFrame]    = useState(0)
  const [playing,  setPlaying]  = useState(false)
  const [speed,    setSpeed]    = useState(1)
  const [bounds,   setBounds]   = useState(null)
  const [hiddenPlayers, setHiddenPlayers] = useState(new Set())
  const [feedCollapsed, setFeedCollapsed] = useState(false)
  const [zoom, setZoom] = useState(1)
  const [pan,  setPan]  = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
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

  const timerRef      = useRef(null)
  const mapImageRef   = useRef(null)
  const canvasWrapRef = useRef(null)
  const dragRef       = useRef({ dragging: false, lastX: 0, lastY: 0 })
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
    const f = tickData.frames || []
    setFrames(f)
    setGrenades(tickData.grenades || [])
    setRoundEvents(tickData.events || [])
    setShots(tickData.shots || [])
    setFrame(0)
    if (!f.length) {
      setOverlay({ show: true, icon: '❌', msg: 'No position data for this round', showDownload: false, downloading: false })
    } else {
      setOverlay({ show: false, icon: '', msg: '', showDownload: false, downloading: false })
    }
  }, [tickData])

  useEffect(() => {
    redraw(frames, frame, bounds, mapImageRef.current, hiddenPlayers, playerColorMap, grenades, zoom, pan, shots)
  }, [frames, frame, bounds, hiddenPlayers, imageVer, playerColorMap, grenades, zoom, pan, shots, redraw])

  const selectRound = useCallback((num) => {
    const val = String(num)
    stopPlayback()
    setFrames([])
    setGrenades([])
    setRoundEvents([])
    setShots([])
    setFrame(0)
    setZoom(1)
    setPan({ x: 0, y: 0 })
    setOverlay(prev => ({
      ...prev,
      show: true,
      icon: '⏳',
      msg:  'Loading…',
      showDownload: false,
    }))
    setSelectedRound(val)
  }, [stopPlayback])

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

  // Non-passive wheel listener for scroll-to-zoom toward cursor
  useEffect(() => {
    const el = canvasWrapRef.current
    if (!el) return
    const onWheel = (e) => {
      e.preventDefault()
      const rect = el.getBoundingClientRect()
      const cx = e.clientX - rect.left
      const cy = e.clientY - rect.top
      const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1
      setZoom(z => {
        const newZ = Math.max(0.25, Math.min(6, z * factor))
        setPan(p => ({
          x: cx + (p.x - cx) * (newZ / z),
          y: cy + (p.y - cy) * (newZ / z),
        }))
        return newZ
      })
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [])

  const handleMouseDown = useCallback((e) => {
    dragRef.current = { dragging: true, lastX: e.clientX, lastY: e.clientY }
    setIsDragging(true)
  }, [])

  const handleMouseMove = useCallback((e) => {
    if (!dragRef.current.dragging) return
    const dx = e.clientX - dragRef.current.lastX
    const dy = e.clientY - dragRef.current.lastY
    dragRef.current.lastX = e.clientX
    dragRef.current.lastY = e.clientY
    setPan(p => ({ x: p.x + dx, y: p.y + dy }))
  }, [])

  const handleMouseUp = useCallback(() => {
    dragRef.current.dragging = false
    setIsDragging(false)
  }, [])

  const elapsed = (frames.length && frames[frame]?.t != null && frames[0]?.t != null)
    ? (frames[frame].t - frames[0].t) / (demo.header?.tickrate || 64)
    : 0

  return (
    <div className={styles.replayWrapper}>

      {/* ── Main grid: left player panel + map canvas ── */}
      <div className={styles.replayLayout}>

        <PlayerPanel
          frames={frames}
          frame={frame}
          scoreboard={scoreboard}
          playerColorMap={playerColorMap}
          hiddenPlayers={hiddenPlayers}
          togglePlayer={togglePlayer}
          selectedRound={selectedRound}
          elapsed={elapsed}
        />

        <div
          ref={canvasWrapRef}
          className={styles.mapCanvasWrapV2}
          style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
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

        <EventFeed
          kills={demo.kills || []}
          grenades={grenades}
          events={roundEvents}
          currentTick={frames[frame]?.t ?? 0}
          roundNum={selectedRound ? parseInt(selectedRound) : null}
          hasRound={!!selectedRound}
          collapsed={feedCollapsed}
          onToggle={() => setFeedCollapsed(c => !c)}
        />

      </div>

      {/* ── Bottom bar: playback + scrubber + round pills ── */}
      <div className={styles.replayBottomBar}>

        <div className={styles.replayControlRow}>
          <div className={styles.replayControls}>
            <button
              className="btn"
              style={playing ? { background: 'var(--ct)', color: '#fff', borderColor: 'var(--ct)' } : {}}
              onClick={() => { if (!frames.length) return; playing ? stopPlayback() : setPlaying(true) }}
              disabled={!frames.length}
            >
              {playing ? '⏸' : '▶'}
            </button>
            <button className="btn" onClick={() => {
              const size = canvasRef.current?.width || 560
              const cx = size / 2, cy = size / 2
              setZoom(z => { const nz = Math.min(6, +(z * 1.25).toFixed(3)); setPan(p => ({ x: cx + (p.x - cx) * (nz / z), y: cy + (p.y - cy) * (nz / z) })); return nz })
            }} title="Zoom in">+</button>
            <span className={styles.zoomLabel}>{(zoom < 1 ? zoom.toFixed(2) : zoom % 1 === 0 ? zoom : +zoom.toFixed(2))}×</span>
            <button className="btn" onClick={() => {
              const size = canvasRef.current?.width || 560
              const cx = size / 2, cy = size / 2
              setZoom(z => { const nz = Math.max(0.25, +(z / 1.25).toFixed(3)); setPan(p => ({ x: cx + (p.x - cx) * (nz / z), y: cy + (p.y - cy) * (nz / z) })); return nz })
            }} title="Zoom out">−</button>
            <button className="btn" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }) }} title="Reset view">⌂</button>
            <select
              className={styles.mapSelect}
              style={{ width: 62 }}
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

          <TimelineScrubber
            frames={frames}
            frame={frame}
            kills={demo.kills || []}
            roundEvents={roundEvents}
            selectedRound={selectedRound}
            onScrub={(f) => { stopPlayback(); setFrame(f) }}
            disabled={!frames.length}
          />
        </div>

        <div className={styles.replayRoundPills}>
          {rounds.map(r => (
            <button
              key={r.round_num}
              className={[
                styles.replayRoundPill,
                String(r.round_num) === selectedRound ? styles.replayRoundPillActive : '',
              ].join(' ')}
              onClick={() => selectRound(r.round_num)}
              disabled={!demo.has_ticks}
              title={`Round ${r.round_num} — ${r.reason}`}
            >
              {r.round_num}
            </button>
          ))}
        </div>

      </div>

    </div>
  )
}
