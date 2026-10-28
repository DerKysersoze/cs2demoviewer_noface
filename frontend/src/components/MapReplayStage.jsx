import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ticksApi } from '../api/ticks'
import { useMapCanvas, worldToCanvas, mapViewport } from '../hooks/useMapCanvas'
import { floorForZ } from './mapFloors'
import styles from './MapReplayStage.module.css'

const EMPTY_HIDDEN = new Set()

// ── Timeline scrubber with kill + bomb markers ───────────────────
function TimelineScrubber({ frames, frame, kills, roundEvents, roundNum, onScrub, onJumpTick, disabled }) {
  const startTick = frames[0]?.t ?? 0
  const endTick   = frames[frames.length - 1]?.t ?? 1
  const range     = endTick - startTick || 1

  const killMarkers = useMemo(() => {
    if (!frames.length || !roundNum) return []
    return kills
      .filter(k => k.round_num === roundNum && k.tick >= startTick && k.tick <= endTick)
      .map(k => ({ tick: k.tick, pct: (k.tick - startTick) / range * 100, hs: k.headshot }))
  }, [kills, roundNum, startTick, endTick, range, frames.length])

  const bombRegion = useMemo(() => {
    if (!frames.length) return null
    const plantEvt   = roundEvents.find(e => e.type === 'plant')
    const resolveEvt = roundEvents.find(e => e.type === 'defuse' || e.type === 'explode')
    if (!plantEvt) return null
    const endT = resolveEvt ? resolveEvt.tick : endTick
    return {
      left:  Math.max(0, (plantEvt.tick - startTick) / range * 100),
      width: Math.min(100, (endT - plantEvt.tick) / range * 100),
    }
  }, [roundEvents, startTick, endTick, range, frames.length])

  return (
    <div className={styles.timeline}>
      {bombRegion && (
        <div
          className={styles.bombRegion}
          style={{ left: `${bombRegion.left}%`, width: `${bombRegion.width}%` }}
        />
      )}
      {killMarkers.map((m, i) => (
        <button
          key={i}
          type="button"
          className={styles.markerHit}
          style={{ left: `${m.pct}%` }}
          onClick={() => onJumpTick?.(m.tick)}
          title="Jump to this kill"
          aria-label="Jump to kill"
        >
          <span className={styles.markerBar} style={{ background: m.hs ? '#facc15' : 'rgb(var(--red))' }} />
        </button>
      ))}
      <input
        type="range"
        className={styles.scrubber}
        min={0}
        max={Math.max(0, frames.length - 1)}
        value={frame}
        onChange={e => onScrub(parseInt(e.target.value))}
        disabled={disabled}
        aria-label="Replay position"
      />
    </div>
  )
}

/**
 * MapReplayStage — the shared 2D replay core (canvas + floor tabs + playback).
 *
 * Used in two places:
 *   - variant="inline" — the Map page, embedded in the
 *     [players | stage | feed] grid; parent keeps the player panel + event feed
 *     and reads {frame, frames, playing} back via onState.  Full interaction:
 *     wheel zoom, drag pan, click-to-follow a player (auto floor switch),
 *     hover tooltip, keyboard shortcuts.
 *   - variant="panel"  — standalone (Results Rounds companion, capped at 520px;
 *     pass `wide` to drop the cap and fill the parent column).
 *
 * Multi-floor: `mapInfo.floors` (from /api/map_info/<map>) lists the available
 * floors sorted by altitude.  Switching floor swaps the map image
 * (maps/<map>_<floor>.png) and hides players that are not on that floor in
 * the current frame (assigned by their z altitude vs the section ranges).
 * While following a player the floor switches automatically with them.
 *
 * Follow mode (inline): `selectedPlayer` + `onSelectPlayer` are parent-owned
 * so the Map page's player panel rows can drive the same selection.
 * Bomb: `bomb` ({x,y,z,plant_tick,defuse_tick} | null, from /api/ticks) is
 * drawn when planted on the active floor.
 */
export default function MapReplayStage({
  tickData = undefined, // {frames, grenades, events, shots, bomb, error} | undefined while loading
  mapName = null,
  kills = [],
  roundNum = null,      // selected round number (kill markers + context)
  hasTicks = true,      // demo has position data at all
  playerColorMap = {},
  hiddenPlayers = EMPTY_HIDDEN, // parent-owned visibility toggles
  variant = 'panel',    // 'panel' | 'inline'
  wide = false,         // 'panel' only: fill the parent column (drop the 520px cap)
  selectedPlayer = null,
  onSelectPlayer = undefined,
  bomb = null,
  onSelectRound = undefined,
  onState,              // ({frame, frames, playing}) → parent panels
}) {
  const frames      = useMemo(() => tickData?.frames || [], [tickData])
  const grenades    = useMemo(() => tickData?.grenades || [], [tickData])
  const roundEvents = useMemo(() => tickData?.events || [], [tickData])
  const shots       = useMemo(() => tickData?.shots || [], [tickData])

  const isInline = variant === 'inline'
  const isPanel  = variant === 'panel'

  // ── map info: bounds (pos_x/pos_y/scale) + floors ─────────────────────
  const { data: mapInfo } = useQuery({
    queryKey: ['map_info', mapName],
    queryFn:  () => ticksApi.getMapInfo(mapName),
    enabled:  !!mapName,
    retry:    false,
  })
  const bounds = mapInfo || null
  const floors = useMemo(() => mapInfo?.floors || [], [mapInfo])

  // ── floor selection ────────────────────────────────────────────────────
  const [activeFloor, setActiveFloor] = useState(null)
  const floor = floors.find(f => f.name === activeFloor)
    || floors.find(f => f.name === 'default')
    || floors[0] || null
  const floorName = floor ? floor.name : 'default'

  // ── playback / view state ──────────────────────────────────────────────
  const [frame, setFrame] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const [imageVer, setImageVer] = useState(0)
  const [overlay, setOverlay] = useState({
    show: false, icon: '', msg: '', showDownload: false, downloading: false,
  })
  const [tooltip, setTooltip] = useState(null)   // {x, y, name, hp, w, alive}
  const [area, setArea] = useState(null)         // inline: measured {w, h} of the canvas area

  const timerRef      = useRef(null)
  const mapImageRef   = useRef(null)
  const canvasAreaRef = useRef(null)
  const canvasWrapRef = useRef(null)
  const dragRef       = useRef({ dragging: false, lastX: 0, lastY: 0 })
  const clickStartRef = useRef(null)             // click-vs-drag discrimination
  const { canvasRef, redraw } = useMapCanvas()

  const stopPlayback = useCallback(() => {
    clearInterval(timerRef.current)
    setPlaying(false)
  }, [])

  // ── playback loop ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!playing || !frames.length) return
    timerRef.current = setInterval(() => {
      setFrame(prev => Math.min(prev + 1, frames.length - 1))
    }, Math.max(16, Math.round(100 / speed)))
    return () => clearInterval(timerRef.current)
  }, [playing, speed, frames.length])

  // Stop cleanly at the last frame — kept out of the updater above so the
  // updater stays pure (StrictMode double-invokes impure updaters).
  useEffect(() => {
    if (playing && frames.length && frame >= frames.length - 1) stopPlayback()
  }, [playing, frame, frames.length, stopPlayback])

  // ── reset when a new round's tick data arrives / is requested ─────────
  useEffect(() => {
    stopPlayback()
    setFrame(0)
    setZoom(1)
    setPan({ x: 0, y: 0 })
    setTooltip(null)
    if (!tickData) {
      setOverlay({
        show: true,
        icon: '⏳',
        msg: hasTicks
          ? (roundNum ? 'Loading…' : 'Select a round to view player positions')
          : 'Position data not available in this demo',
        showDownload: false,
        downloading: false,
      })
    } else if (tickData.error) {
      setOverlay({ show: true, icon: '❌', msg: tickData.error, showDownload: false, downloading: false })
    } else if (!frames.length) {
      setOverlay({ show: true, icon: '❌', msg: 'No position data for this round', showDownload: false, downloading: false })
    } else {
      setOverlay({ show: false, icon: '', msg: '', showDownload: false, downloading: false })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tickData])

  // ── map image (per floor) + download fallback ─────────────────────────
  const { data: mapsReadyData } = useQuery({
    queryKey: ['maps_ready'],
    queryFn:  ticksApi.mapsReady,
    retry:    false,
  })

  const loadMapImage = useCallback((name, flr, bustCache) => {
    const img = new Image()
    img.onload  = () => { mapImageRef.current = img; setImageVer(v => v + 1) }
    img.onerror = () => { mapImageRef.current = null }
    img.src = ticksApi.mapImageUrl(name, flr) + (bustCache ? `?t=${Date.now()}` : '')
  }, [])

  useEffect(() => {
    if (!mapName) return
    if (mapsReadyData?.ready) {
      loadMapImage(mapName, floorName, false)
    } else if (mapsReadyData) {
      setOverlay(o => ({ ...o, icon: '⬇️', msg: 'Map radar images not downloaded yet.', showDownload: true }))
    }
  }, [mapsReadyData, mapName, floorName, loadMapImage])

  const handleDownload = () => {
    setOverlay(o => ({ ...o, icon: '⏳', msg: 'Downloading map images, please wait…', downloading: true }))
    ticksApi.downloadMaps()
      .then(d => {
        if (d.error) {
          setOverlay(o => ({ ...o, icon: '❌', msg: `Download failed: ${d.error}`, downloading: false }))
        } else {
          setOverlay(o => ({ ...o, icon: '✅', msg: 'Maps downloaded! Select a round to begin.', showDownload: false, downloading: false }))
          if (mapName) loadMapImage(mapName, floorName, true)
        }
      })
      .catch(() =>
        setOverlay(o => ({ ...o, icon: '❌', msg: 'Network error during download.', downloading: false }))
      )
  }

  // ── per-frame floor visibility ─────────────────────────────────────────
  const currentFrame = frames.length ? frames[Math.min(frame, frames.length - 1)] : null

  const floorOfPlayer = useMemo(() => {
    const m = {}
    if (currentFrame && floors.length) {
      for (const pl of currentFrame.p) m[pl.n] = floorForZ(pl.z, floors, 'default')
    }
    return m
  }, [currentFrame, floors])

  // Merge parent-hidden players with players not on the active floor.
  const hiddenForDraw = useMemo(() => {
    if (!floors.length) return hiddenPlayers
    const s = new Set(hiddenPlayers)
    for (const [name, fn] of Object.entries(floorOfPlayer)) {
      if (fn !== floorName) s.add(name)
    }
    return s
  }, [hiddenPlayers, floorOfPlayer, floorName, floors.length])

  // Players per floor for the current frame (tab badges + band header)
  const floorCounts = useMemo(() => {
    const c = {}
    for (const f of floors) c[f.name] = 0
    for (const fn of Object.values(floorOfPlayer)) if (c[fn] != null) c[fn] += 1
    return c
  }, [floors, floorOfPlayer])

  // ── bomb (planted site, only while planted on the active floor) ───────
  const activeBomb = useMemo(() => {
    if (!bomb || bomb.x == null || !currentFrame) return null
    const t = currentFrame.t
    if (t < bomb.plant_tick) return null
    if (bomb.defuse_tick != null && t > bomb.defuse_tick + 16) return null
    if (floors.length) {
      const fn = floorForZ(bomb.z, floors, 'default')
      if (fn !== floorName) return null
    }
    return bomb
  }, [bomb, currentFrame, floors, floorName])

  // ── FOLLOW MODE ────────────────────────────────────────────────────────
  // Selected player: camera recenters on them every frame (smooth at the
  // frame cadence), zoom is preserved, and the floor auto-switches when they
  // move to another level.  Death releases the selection (parent state).
  useEffect(() => {
    if (!isInline || !selectedPlayer || !bounds || !frames.length) return
    const f  = frames[Math.min(frame, frames.length - 1)]
    const pl = f?.p?.find(p => p.n === selectedPlayer)
    if (!pl) return
    if (!pl.alive) {
      onSelectPlayer?.(null)
      return
    }
    // Auto floor switch
    if (floors.length) {
      const fn = floorForZ(pl.z, floors, 'default')
      if (fn !== floorName) setActiveFloor(fn)
    }
    // Center camera on the player (keeps the user's zoom level)
    const w = canvasWrapRef.current?.clientWidth || 0
    const h = canvasWrapRef.current?.clientHeight || 0
    if (w && h) {
      const { size, ox, oy } = mapViewport(w, h)
      const base = worldToCanvas(pl.x, pl.y, bounds, size)
      setPan({ x: w / 2 - (ox + base.x * zoom), y: h / 2 - (oy + base.y * zoom) })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isInline, selectedPlayer, frame, bounds, frames, floors, floorName, zoom])

  // ── draw ───────────────────────────────────────────────────────────────
  useEffect(() => {
    redraw(frames, frame, bounds, mapImageRef.current, hiddenForDraw, playerColorMap, grenades, zoom, pan, shots, {
      selectedPlayer: isInline ? selectedPlayer : null,
      bomb: activeBomb,
    })
  }, [frames, frame, bounds, hiddenForDraw, imageVer, playerColorMap, grenades, zoom, pan, shots, area, redraw, isInline, selectedPlayer, activeBomb])

  // ── feed frame/playing state up to parent panels ──────────────────────
  useEffect(() => {
    onState?.({ frame, frames, playing })
  }, [frame, frames, playing, onState])

  // ── inline: fill the canvas area (full column width × height) ─────────
  // The map region inside stays min(w,h)-scaled & centered (see mapViewport),
  // so the map keeps its size while the extra space becomes pan room.
  useEffect(() => {
    if (!isInline) return undefined
    const el = canvasAreaRef.current
    if (!el || typeof ResizeObserver === 'undefined') return undefined
    const ro = new ResizeObserver(() => {
      const w = el.clientWidth, h = el.clientHeight
      if (w > 0 && h > 0) setArea({ w, h })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [isInline])

  // ── zoom / pan ─────────────────────────────────────────────────────────
  // The panel variant (Results band) is a STATIC map: zoom in/out only, no
  // wheel hijack, no drag-pan — the image stays put and scales around the
  // canvas center.  The inline variant (Map page) keeps the full replay
  // camera: scroll-to-zoom toward the cursor + drag-pan + click-to-select.
  const MIN_ZOOM = isPanel ? 1 : 0.5
  const MAX_ZOOM = isPanel ? 4 : 12

  // Zoom anchored at `anchor` (default: canvas center) so that point stays
  // fixed on screen: pan' = anchor + (pan − anchor) · (z'/z).
  // Both setters are called once, outside any updater (pure updaters —
  // StrictMode double-invokes impure ones, which used to double-apply the
  // pan compensation and make the map drift on every zoom).
  const zoomAt = useCallback((factor, anchor = null) => {
    const w = canvasRef.current?.width || 560
    const h = canvasRef.current?.height || 560
    const cx = anchor ? anchor.x : w / 2
    const cy = anchor ? anchor.y : h / 2
    const nz = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, +(zoom * factor).toFixed(3)))
    if (nz === zoom) return
    const k = nz / zoom
    setPan({ x: cx + (pan.x - cx) * k, y: cy + (pan.y - cy) * k })
    setZoom(nz)
  }, [zoom, pan, canvasRef, MIN_ZOOM, MAX_ZOOM])

  // Non-passive wheel listener for scroll-to-zoom toward the cursor
  // (inline variant only — the static panel lets the page scroll).
  useEffect(() => {
    if (isPanel) return undefined
    const el = canvasWrapRef.current
    if (!el) return undefined
    const onWheel = (e) => {
      e.preventDefault()
      const rect = el.getBoundingClientRect()
      zoomAt(e.deltaY < 0 ? 1.1 : 1 / 1.1, {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      })
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [isPanel, zoomAt])

  // ── hit testing (click-to-follow + hover tooltip) ─────────────────────
  const hitTest = useCallback((mx, my, threshold) => {
    const f = frames.length ? frames[Math.min(frame, frames.length - 1)] : null
    if (!f || !bounds) return null
    const w = canvasWrapRef.current?.clientWidth || 0
    const h = canvasWrapRef.current?.clientHeight || 0
    if (!w || !h) return null
    const { size, ox, oy } = mapViewport(w, h)
    let best = null
    let bestD = threshold
    for (const pl of f.p) {
      if (hiddenForDraw.has(pl.n)) continue
      const base = worldToCanvas(pl.x, pl.y, bounds, size)
      const sx = ox + base.x * zoom + pan.x
      const sy = oy + base.y * zoom + pan.y
      const d = Math.hypot(mx - sx, my - sy)
      if (d < bestD) { bestD = d; best = pl }
    }
    return best
  }, [frames, frame, bounds, hiddenForDraw, zoom, pan])

  const handleMouseDown = useCallback((e) => {
    if (isPanel) return
    clickStartRef.current = { x: e.clientX, y: e.clientY }
    dragRef.current = { dragging: true, lastX: e.clientX, lastY: e.clientY }
    setIsDragging(true)
  }, [isPanel])

  const handleMouseMove = useCallback((e) => {
    if (isPanel) return
    if (dragRef.current.dragging) {
      const dx = e.clientX - dragRef.current.lastX
      const dy = e.clientY - dragRef.current.lastY
      dragRef.current.lastX = e.clientX
      dragRef.current.lastY = e.clientY
      setPan(p => ({ x: p.x + dx, y: p.y + dy }))
      setTooltip(null)
      return
    }
    // Hover tooltip (inline only)
    const rect = canvasWrapRef.current?.getBoundingClientRect()
    if (!rect) return
    const pl = hitTest(e.clientX - rect.left, e.clientY - rect.top, 16)
    if (pl) {
      setTooltip({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
        name: pl.n, hp: pl.hp, w: pl.w, alive: pl.alive,
      })
    } else {
      setTooltip(null)
    }
  }, [isPanel, hitTest])

  const handleMouseUp = useCallback((e) => {
    if (isPanel) {
      dragRef.current.dragging = false
      setIsDragging(false)
      return
    }
    const cs = clickStartRef.current
    clickStartRef.current = null
    dragRef.current.dragging = false
    setIsDragging(false)
    // Click (not a drag) on the inline map → select/deselect the player.
    if (cs && e.button === 0 && Math.hypot(e.clientX - cs.x, e.clientY - cs.y) < 5) {
      const rect = canvasWrapRef.current?.getBoundingClientRect()
      if (!rect) return
      const pl = hitTest(e.clientX - rect.left, e.clientY - rect.top, 18)
      if (pl) {
        onSelectPlayer?.(pl.n === selectedPlayer ? null : pl.n)
      } else {
        onSelectPlayer?.(null)
      }
    }
  }, [isPanel, hitTest, onSelectPlayer, selectedPlayer])

  const handleMouseLeave = useCallback(() => {
    clickStartRef.current = null
    dragRef.current.dragging = false
    setIsDragging(false)
    setTooltip(null)
  }, [])

  // ── jump to a tick (clickable kill markers) ────────────────────────────
  const jumpToTick = useCallback((tick) => {
    if (!frames.length) return
    let best = 0
    let bd = Infinity
    frames.forEach((f, i) => {
      const d = Math.abs(f.t - tick)
      if (d < bd) { bd = d; best = i }
    })
    stopPlayback()
    setFrame(best)
  }, [frames, stopPlayback])

  // ── keyboard shortcuts (inline only) ───────────────────────────────────
  // Space play/pause · ←/→ step · 1-9 round · +/− zoom · 0 reset · Esc release
  useEffect(() => {
    if (!isInline) return undefined
    const onKey = (e) => {
      const t = e.target
      if (t && (t.tagName === 'INPUT' || t.tagName === 'SELECT' || t.tagName === 'TEXTAREA')) return
      if (e.metaKey || e.ctrlKey || e.altKey) return
      switch (e.key) {
        case ' ':
          e.preventDefault()
          if (!frames.length) return
          if (playing) stopPlayback()
          else setPlaying(true)
          break
        case 'ArrowLeft':
          e.preventDefault()
          stopPlayback()
          setFrame(f => Math.max(0, f - 1))
          break
        case 'ArrowRight':
          e.preventDefault()
          stopPlayback()
          setFrame(f => Math.min(frames.length - 1, f + 1))
          break
        case '+': case '=':
          zoomAt(1.25)
          break
        case '-': case '_':
          zoomAt(1 / 1.25)
          break
        case '0':
          setZoom(1)
          setPan({ x: 0, y: 0 })
          break
        case 'Escape':
          onSelectPlayer?.(null)
          break
        default:
          if (/^[1-9]$/.test(e.key) && onSelectRound) onSelectRound(parseInt(e.key, 10))
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [isInline, frames.length, playing, zoomAt, stopPlayback, onSelectPlayer, onSelectRound])

  const zoomLabel = zoom < 1 ? zoom.toFixed(2) : (zoom % 1 === 0 ? zoom : +zoom.toFixed(2))

  // Inline stage wrap: explicit measured w×h, CSS aspect-ratio fallback.
  const stageWrapStyle = isInline && area
    ? { width: area.w, height: area.h }
    : undefined

  return (
    <div
      className={`${styles.stage}${isInline ? ' ' + styles.stageInline : ''}${wide && !isInline ? ' ' + styles.stageWide : ''}`.trim()}
    >

      {floors.length > 1 && (
        <div className={styles.floorRow}>
          <div className={styles.floorTabs} role="tablist" aria-label="Map floor">
            {floors.map(f => (
              <button
                key={f.name}
                type="button"
                role="tab"
                aria-selected={f.name === floorName}
                className={`${styles.floorTab} ${f.name === floorName ? styles.floorTabActive : ''}`}
                onClick={() => setActiveFloor(f.name)}
              >
                {f.label}
                <span className={styles.floorTabCount}>{floorCounts[f.name] ?? 0}</span>
              </button>
            ))}
          </div>
          <span className={styles.floorHint}>
            {isInline && selectedPlayer ? 'following player — auto floor' : 'players on this floor'}
          </span>
        </div>
      )}

      <div ref={canvasAreaRef} className={styles.canvasArea}>
        <div
          ref={canvasWrapRef}
          className={styles.stageWrap}
          style={stageWrapStyle}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseLeave}
        >
          <canvas ref={canvasRef} className={styles.mapCanvas} />
          {overlay.show && (
            <div className={styles.overlay}>
              <span className={styles.overlayIcon}>{overlay.icon}</span>
              <span className={styles.overlayMsg}>{overlay.msg}</span>
              {overlay.showDownload && (
                <button
                  className="btn btn-ghost"
                  style={{ background: 'rgb(var(--paper))' }}
                  onClick={handleDownload}
                  disabled={overlay.downloading}
                >
                  {overlay.downloading ? 'Downloading…' : 'Download Map Images (~100 MB)'}
                </button>
              )}
            </div>
          )}
          {isInline && tooltip && !overlay.show && (
            <div
              className={styles.tooltip}
              style={{ left: tooltip.x, top: tooltip.y }}
            >
              <strong>{tooltip.name}</strong>
              <span>{tooltip.alive ? `HP ${tooltip.hp}` : 'DEAD'}</span>
              {tooltip.w && <span className={styles.tooltipWep}>{tooltip.w}</span>}
            </div>
          )}
        </div>
      </div>

      <div className={styles.playback}>
        <div className={styles.controls}>
          <button
            className="btn"
            style={playing ? { background: 'rgb(var(--ct))', color: '#fff', borderColor: 'rgb(var(--ct))' } : {}}
            onClick={() => { if (!frames.length) return; playing ? stopPlayback() : setPlaying(true) }}
            disabled={!frames.length}
            aria-label={playing ? 'Pause' : 'Play'}
            title={playing ? 'Pause (Space)' : 'Play (Space)'}
          >
            {playing ? '⏸' : '▶'}
          </button>
          <button className="btn" onClick={() => zoomAt(1.25)} title="Zoom in (+)" disabled={isPanel && zoom >= MAX_ZOOM}>+</button>
          <span className={styles.zoomLabel}>{zoomLabel}×</span>
          <button className="btn" onClick={() => zoomAt(1 / 1.25)} title="Zoom out (−)" disabled={isPanel && zoom <= MIN_ZOOM}>−</button>
          <button className="btn" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }) }} title="Reset view (0)">⌂</button>
          <select
            className={styles.speed}
            value={speed}
            aria-label="Playback speed"
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
          {isInline && selectedPlayer && (
            <span className={styles.followChip} title="Following this player — click ✕ or press Esc to release">
              🎯 {selectedPlayer.substring(0, 24)}
              <button type="button" onClick={() => onSelectPlayer?.(null)} aria-label="Stop following">✕</button>
            </span>
          )}
        </div>

        <TimelineScrubber
          frames={frames}
          frame={frame}
          kills={kills}
          roundEvents={roundEvents}
          roundNum={roundNum}
          onScrub={(f) => { stopPlayback(); setFrame(f) }}
          onJumpTick={jumpToTick}
          disabled={!frames.length}
        />
      </div>

    </div>
  )
}