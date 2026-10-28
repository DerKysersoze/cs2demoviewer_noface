import { useRef, useCallback } from 'react'

const TRAIL_LEN = 12

// Grenade rendering config
const NADE_STYLE = {
  smoke: { fill: 'rgba(160,160,170,0.55)', stroke: 'rgba(220,220,230,0.90)', radius: 200 },
  fire:  { fill: 'rgba(255,90,0,0.60)',    stroke: 'rgba(255,160,0,0.90)',   radius: 160 },
  flash: { fill: 'rgba(255,245,100,0.80)', stroke: 'rgba(255,255,200,1.0)',  radius: 80  },
  he:    { fill: 'rgba(220,60,0,0.75)',    stroke: 'rgba(255,120,40,1.0)',   radius: 100 },
}

export function worldToCanvas(wx, wy, bounds, size) {
  return {
    x: ((wx - bounds.pos_x) / bounds.scale / 1024) * size,
    y: ((bounds.pos_y - wy) / bounds.scale / 1024) * size,
  }
}

// Map viewport for a rectangular canvas: the (square) map region is scaled to
// min(w, h) and centered; ox/oy offset the map area inside the canvas.
// Square canvases give ox = oy = 0 → identical to the old behavior.
export function mapViewport(w, h) {
  const size = Math.min(w, h)
  return { size, ox: (w - size) / 2, oy: (h - size) / 2 }
}

// Convert a world-unit radius to canvas pixels
function worldRadiusToPx(r, bounds, size) {
  return (r / bounds.scale / 1024) * size
}

/**
 * redraw(frames, frameIdx, bounds, mapImage, hiddenPlayers, playerColorMap,
 *          grenades, zoom, pan, shots, viewOpts)
 *
 * viewOpts = {
 *   selectedPlayer: name | null — highlight + full opacity; other players dimmed
 *   bomb:           {x, y, z} | null — planted-bomb marker (world coords)
 * }
 *
 * Dot radius, rings, trails, tracers and labels are scaled by 1/zoom so they
 * keep a constant ON-SCREEN size at any zoom level (readability at 12×).
 * World-sized objects (grenade radii, map image) scale with zoom as before.
 */
export function useMapCanvas() {
  const canvasRef = useRef(null)

  const redraw = useCallback((frames, frameIdx, bounds, mapImage, hiddenPlayers, playerColorMap, grenades, zoom = 1, pan = { x: 0, y: 0 }, shots = [], viewOpts = {}) => {
    const canvas = canvasRef.current
    if (!canvas) return

    const w = canvas.parentElement?.clientWidth || 560
    const h = canvas.parentElement?.clientHeight || 560
    const { size, ox, oy } = mapViewport(w, h)
    canvas.width  = w
    canvas.height = h
    const ctx = canvas.getContext('2d')

    const { selectedPlayer = null, bomb = null } = viewOpts

    ctx.fillStyle = '#0a0a10'
    ctx.fillRect(0, 0, w, h)

    // ox/oy center the map region when the canvas is wider/taller than it is
    // deep (full-width map page).  Everything drawn below uses worldToCanvas
    // with `size`, so the single translate carries the offset everywhere.
    ctx.save()
    ctx.translate(ox + pan.x, oy + pan.y)
    ctx.scale(zoom, zoom)

    if (mapImage) {
      ctx.globalAlpha = 0.55
      ctx.drawImage(mapImage, 0, 0, size, size)
      ctx.globalAlpha = 1
    }

    if (!frames.length || !bounds) {
      ctx.restore()
      return
    }
    const frame = frames[frameIdx]
    if (!frame) return

    // Constant on-screen size: divide by zoom so r * zoom ≈ const
    const inv = 1 / zoom
    const dim = (name) => (!selectedPlayer || name === selectedPlayer ? 1 : 0.42)

    // ── Grenades (world-sized — scale with zoom) ─────────────
    if (grenades?.length) {
      const currentTick = frame.t
      grenades.forEach(g => {
        if (currentTick < g.from_tick || currentTick > g.to_tick) return
        const style = NADE_STYLE[g.type]
        if (!style) return
        const pos = worldToCanvas(g.x, g.y, bounds, size)
        const r   = worldRadiusToPx(style.radius, bounds, size)
        ctx.beginPath()
        ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2)
        ctx.fillStyle = style.fill
        ctx.fill()
        ctx.strokeStyle = style.stroke
        ctx.lineWidth   = 1.5 * inv
        ctx.stroke()
      })
      ctx.globalAlpha = 1
    }

    // ── Tracers ──────────────────────────────────────────────
    // Frames are sampled 1-in-8 ticks, so use a wide enough window (~2s at 64hz = 128 ticks).
    // CS2 yaw: 0°=east, CCW positive, stored in degrees.
    // worldToCanvas flips Y (pos_y - wy), so +Y game = -Y canvas → sin component negated.
    if (shots?.length) {
      const currentTick   = frame.t
      const TRACER_TICKS  = 128  // ~2 seconds at 64 hz
      const TRACER_LENGTH = 2000 // world units

      shots.forEach(s => {
        const age = currentTick - s.tick
        if (age < 0 || age > TRACER_TICKS) return
        if (hiddenPlayers.has(s.player)) return
        if (selectedPlayer && s.player !== selectedPlayer) return // tracers only for the followed player

        const fade  = 1 - age / TRACER_TICKS
        const color = playerColorMap[s.player] || '#fff'

        // Use current-frame position so tracer is anchored to the visible player dot
        const shooterFrame = frame.p.find(pl => pl.n === s.player)
        const from = shooterFrame
          ? worldToCanvas(shooterFrame.x, shooterFrame.y, bounds, size)
          : worldToCanvas(s.x, s.y, bounds, size)

        // CS2 yaw: 0°=East, CCW positive. worldToCanvas already handles Y-flip
        // (pos_y - wy), so we use +sin — no pre-negation needed.
        const radYaw = (s.yaw * Math.PI) / 180
        const wx2 = s.x + Math.cos(radYaw) * TRACER_LENGTH
        const wy2 = s.y + Math.sin(radYaw) * TRACER_LENGTH
        const to  = worldToCanvas(wx2, wy2, bounds, size)

        ctx.beginPath()
        ctx.moveTo(from.x, from.y)
        ctx.lineTo(to.x, to.y)
        ctx.strokeStyle = color
        ctx.lineWidth   = 1.8 * inv
        ctx.globalAlpha = fade * 0.9
        ctx.stroke()
      })
      ctx.globalAlpha = 1
    }

    // ── Trails ──────────────────────────────────────────────
    const trails = {}
    for (let fi = Math.max(0, frameIdx - TRAIL_LEN); fi <= frameIdx; fi++) {
      const f = frames[fi]
      if (!f) continue
      f.p.forEach(pl => {
        if (!trails[pl.n]) trails[pl.n] = []
        trails[pl.n].push({ ...pl, fi })
      })
    }
    Object.entries(trails).forEach(([name, pts]) => {
      if (hiddenPlayers.has(name)) return
      const color = playerColorMap[name] || '#fff'
      const alphaScale = dim(name)
      for (let i = 1; i < pts.length; i++) {
        if (!pts[i - 1].alive || !pts[i].alive) continue
        const ca = worldToCanvas(pts[i - 1].x, pts[i - 1].y, bounds, size)
        const cb = worldToCanvas(pts[i].x, pts[i].y, bounds, size)
        ctx.beginPath()
        ctx.strokeStyle = color
        ctx.globalAlpha = (0.12 + 0.55 * (i / pts.length)) * alphaScale
        ctx.lineWidth   = 1.5 * inv
        ctx.moveTo(ca.x, ca.y)
        ctx.lineTo(cb.x, cb.y)
        ctx.stroke()
      }
    })
    ctx.globalAlpha = 1

    // ── Players ──────────────────────────────────────────────
    // Draw non-selected first, selected last (so its glow sits on top).
    const ordered = [...frame.p].sort((a, b) =>
      (a.n === selectedPlayer ? 1 : 0) - (b.n === selectedPlayer ? 1 : 0))
    ordered.forEach(pl => {
      if (hiddenPlayers.has(pl.n)) return
      const color = playerColorMap[pl.n] || '#fff'
      const pos   = worldToCanvas(pl.x, pl.y, bounds, size)
      const r     = 7 * inv
      const isSel = pl.n === selectedPlayer
      const a     = dim(pl.n)

      if (!pl.alive) {
        ctx.strokeStyle = color
        ctx.globalAlpha = 0.35 * a
        ctx.lineWidth   = 2 * inv
        ctx.beginPath(); ctx.moveTo(pos.x - 4 * inv, pos.y - 4 * inv); ctx.lineTo(pos.x + 4 * inv, pos.y + 4 * inv); ctx.stroke()
        ctx.beginPath(); ctx.moveTo(pos.x + 4 * inv, pos.y - 4 * inv); ctx.lineTo(pos.x - 4 * inv, pos.y + 4 * inv); ctx.stroke()
        ctx.globalAlpha = 1
        return
      }

      // Selection glow (outermost)
      if (isSel) {
        ctx.beginPath()
        ctx.arc(pos.x, pos.y, r + 11 * inv, 0, Math.PI * 2)
        ctx.strokeStyle = 'rgba(255,255,255,0.30)'
        ctx.lineWidth   = 4 * inv
        ctx.stroke()
        ctx.beginPath()
        ctx.arc(pos.x, pos.y, r + 7 * inv, 0, Math.PI * 2)
        ctx.strokeStyle = 'rgba(255,255,255,0.95)'
        ctx.lineWidth   = 1.6 * inv
        ctx.stroke()
      }

      // Side ring (CT = blue, T = yellow)
      ctx.beginPath()
      ctx.arc(pos.x, pos.y, r + 5 * inv, 0, Math.PI * 2)
      ctx.strokeStyle = (pl.side || '').toUpperCase().includes('CT') ? '#38bdf8' : '#fbbf24'
      ctx.lineWidth   = 2.5 * inv
      ctx.globalAlpha = a
      ctx.stroke()

      // HP arc
      ctx.beginPath()
      ctx.arc(pos.x, pos.y, r + 2.5 * inv, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * Math.min(1, (pl.hp || 0) / 100))
      ctx.strokeStyle = color
      ctx.lineWidth   = 2.5 * inv
      ctx.globalAlpha = 0.7 * a
      ctx.stroke()

      // Fill dot
      ctx.beginPath()
      ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2)
      ctx.fillStyle   = color
      ctx.globalAlpha = 0.9 * a
      ctx.fill()

      // Name label (selected: always full opacity, slightly larger)
      ctx.font      = `bold ${Math.round((isSel ? 10 : 9) * inv)}px sans-serif`
      ctx.textAlign = 'center'
      ctx.fillStyle   = isSel ? '#fff' : '#fff'
      ctx.globalAlpha = (isSel ? 1 : 0.9) * a
      ctx.fillText(pl.n.split(' ')[0].substring(0, 8), pos.x, pos.y - r - 4 * inv)
      ctx.globalAlpha = 1
    })

    // ── Planted bomb ─────────────────────────────────────────
    if (bomb && bomb.x != null && bomb.y != null) {
      const pos = worldToCanvas(bomb.x, bomb.y, bounds, size)

      // Blast-area hint ring (world-sized, ~C4 radius)
      ctx.beginPath()
      ctx.arc(pos.x, pos.y, worldRadiusToPx(340, bounds, size), 0, Math.PI * 2)
      ctx.setLineDash([4 * inv, 5 * inv])
      ctx.strokeStyle = 'rgba(239,68,68,0.38)'
      ctx.lineWidth   = 1.5 * inv
      ctx.stroke()
      ctx.setLineDash([])

      // Halo pulse (static double ring)
      ctx.beginPath()
      ctx.arc(pos.x, pos.y, 16 * inv, 0, Math.PI * 2)
      ctx.strokeStyle = 'rgba(239,68,68,0.35)'
      ctx.lineWidth   = 2 * inv
      ctx.stroke()

      // Core
      ctx.beginPath()
      ctx.arc(pos.x, pos.y, 9 * inv, 0, Math.PI * 2)
      ctx.fillStyle   = '#111827'
      ctx.globalAlpha = 1
      ctx.fill()
      ctx.strokeStyle = 'rgba(248,113,113,0.95)'
      ctx.lineWidth   = 2 * inv
      ctx.stroke()

      ctx.font = `${Math.round(11 * inv)}px sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText('💣', pos.x, pos.y + inv)
      ctx.textBaseline = 'alphabetic'

      ctx.font = `bold ${Math.round(8 * inv)}px sans-serif`
      ctx.fillStyle = 'rgba(252,165,165,0.95)'
      ctx.fillText('BOMB', pos.x, pos.y - 18 * inv)
    }

    ctx.restore()
  }, [])

  return { canvasRef, redraw }
}