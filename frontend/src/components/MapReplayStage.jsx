import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ticksApi } from '../api/ticks'
import { useMapCanvas } from '../hooks/useMapCanvas'
import { floorForZ } from './mapFloors'
import styles from './MapReplayStage.module.css'

const EMPTY_HIDDEN = new Set()

// ── Timeline scrubber with kill + bomb markers ───────────────────
function TimelineScrubber({ frames, frame, kills, roundEvents, roundNum, onScrub, disabled }) {
  const startTick = frames[0]?.t ?? 0
  const endTick   = frames[frames.length - 1]?.t ?? 1
  const range     = endTick - startTick || 1

  const killMarkers = useMemo(() => {
    if (!frames.length || !roundNum) return []
    return kills
      .filter(k => k.round_num === roundNum && k.tick >= startTick && k.tick <= endTick)
      .map(k => ({ pct: (k.tick - startTick) / range * 100, hs: k.headshot }))
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
        <div
          key={i}
          className={styles.marker}
          style={{ left: `${m.pct}%`, background: m.hs ? '#facc15' : 'rgb(var(--red))' }}
        />
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
 *     and reads {frame, frames, playing} back via onState.
 *   - variant="panel"  — standalone (Results Rounds companion, capped at 520px;
 *     pass `wide` to drop the cap and fill the parent column).
 *
 * Multi-floor: `mapInfo.floors` (from /api/map_info/<map>) lists the available
 * floors sorted by altitude. Switching floor swaps the map image
 * (maps/<map>_<floor>.png) and hides players that are not on that floor in
 * the current frame (assigned by their z altitude vs the section ranges).
 */
export default function MapReplayStage({
  tickData = undefined, // {frames, grenades, events, shots, error} | undefined while loading
  mapName = null,
  kills = [],
  roundNum = null,      // selected round number (kill markers + context)
  hasTicks = true,      // demo has position data at all
  playerColorMap = {},
  hiddenPlayers = EMPTY_HIDDEN, // parent-owned visibility toggles
  variant = 'panel',    // 'panel' | 'inline'
  wide = false,         // 'panel' only: fill the parent column (drop the 520px cap)
  onState,              // ({frame, frames, playing}) → parent panels
}) {
  const frames      = useMemo(() => tickData?.frames || [], [tickData])
  const grenades    = useMemo(() => tickData?.grenades || [], [tickData])
  const roundEvents = useMemo(() => tickData?.events || [], [tickData])
  const shots       = useMemo(() => tickData?.shots || [], [tickData])

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

  const timerRef      = useRef(null)
  const mapImageRef   = useRef(null)
  const canvasWrapRef = useRef(null)
  const dragRef       = useRef({ dragging: false, lastX: 0, lastY: 0 })
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

  // ── draw ───────────────────────────────────────────────────────────────
  useEffect(() => {
    redraw(frames, frame, bounds, mapImageRef.current, hiddenForDraw, playerColorMap, grenades, zoom, pan, shots)
  }, [frames, frame, bounds, hiddenForDraw, imageVer, playerColorMap, grenades, zoom, pan, shots, redraw])

  // ── feed frame/playing state up to parent panels ──────────────────────
  useEffect(() => {
    onState?.({ frame, frames, playing })
  }, [frame, frames, playing, onState])

  // ── zoom / pan ─────────────────────────────────────────────────────────
  // The panel variant (Results band) is a STATIC map: zoom in/out only, no
  // wheel hijack, no drag-pan — the image stays put and scales around the
  // canvas center.  The inline variant (Viewer tab) keeps the full replay
  // camera: scroll-to-zoom toward the cursor + drag-pan.
  const isPanel  = variant === 'panel'
  const MIN_ZOOM = isPanel ? 1 : 0.25
  const MAX_ZOOM = isPanel ? 4 : 6

  // Zoom anchored at `anchor` (default: canvas center) so that point stays
  // fixed on screen: pan' = anchor + (pan − anchor) · (z'/z).
  // Both setters are called once, outside any updater (pure updaters —
  // StrictMode double-invokes impure ones, which used to double-apply the
  // pan compensation and make the map drift on every zoom).
  const zoomAt = useCallback((factor, anchor = null) => {
    const size = canvasRef.current?.width || 560
    const cx = anchor ? anchor.x : size / 2
    const cy = anchor ? anchor.y : size / 2
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

  const handleMouseDown = useCallback((e) => {
    if (isPanel) return
    dragRef.current = { dragging: true, lastX: e.clientX, lastY: e.clientY }
    setIsDragging(true)
  }, [isPanel])

  const handleMouseMove = useCallback((e) => {
    if (isPanel || !dragRef.current.dragging) return
    const dx = e.clientX - dragRef.current.lastX
    const dy = e.clientY - dragRef.current.lastY
    dragRef.current.lastX = e.clientX
    dragRef.current.lastY = e.clientY
    setPan(p => ({ x: p.x + dx, y: p.y + dy }))
  }, [isPanel])

  const handleMouseUp = useCallback(() => {
    dragRef.current.dragging = false
    setIsDragging(false)
  }, [])

  const zoomLabel = zoom < 1 ? zoom.toFixed(2) : (zoom % 1 === 0 ? zoom : +zoom.toFixed(2))

  const isInline = variant === 'inline'

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
          <span className={styles.floorHint}>players on this floor</span>
        </div>
      )}

      <div
        ref={canvasWrapRef}
        className={styles.stageWrap}
        style={{ cursor: isPanel ? 'default' : isDragging ? 'grabbing' : 'grab' }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
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
      </div>

      <div className={styles.playback}>
        <div className={styles.controls}>
          <button
            className="btn"
            style={playing ? { background: 'rgb(var(--ct))', color: '#fff', borderColor: 'rgb(var(--ct))' } : {}}
            onClick={() => { if (!frames.length) return; playing ? stopPlayback() : setPlaying(true) }}
            disabled={!frames.length}
            aria-label={playing ? 'Pause' : 'Play'}
          >
            {playing ? '⏸' : '▶'}
          </button>
          <button className="btn" onClick={() => zoomAt(1.25)} title="Zoom in" disabled={isPanel && zoom >= MAX_ZOOM}>+</button>
          <span className={styles.zoomLabel}>{zoomLabel}×</span>
          <button className="btn" onClick={() => zoomAt(1 / 1.25)} title="Zoom out" disabled={isPanel && zoom <= MIN_ZOOM}>−</button>
          <button className="btn" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }) }} title="Reset view">⌂</button>
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
        </div>

        <TimelineScrubber
          frames={frames}
          frame={frame}
          kills={kills}
          roundEvents={roundEvents}
          roundNum={roundNum}
          onScrub={(f) => { stopPlayback(); setFrame(f) }}
          disabled={!frames.length}
        />
      </div>

    </div>
  )
}
