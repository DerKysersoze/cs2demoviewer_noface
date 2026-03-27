import { useRef, useCallback } from 'react'

const TRAIL_LEN = 12

// Grenade rendering config
const NADE_STYLE = {
  smoke: { fill: 'rgba(160,160,170,0.55)', stroke: 'rgba(220,220,230,0.90)', radius: 200 },
  fire:  { fill: 'rgba(255,90,0,0.60)',    stroke: 'rgba(255,160,0,0.90)',   radius: 160 },
  flash: { fill: 'rgba(255,245,100,0.80)', stroke: 'rgba(255,255,200,1.0)',  radius: 80  },
  he:    { fill: 'rgba(220,60,0,0.75)',    stroke: 'rgba(255,120,40,1.0)',   radius: 100 },
}

function worldToCanvas(wx, wy, bounds, size) {
  return {
    x: ((wx - bounds.pos_x) / bounds.scale / 1024) * size,
    y: ((bounds.pos_y - wy) / bounds.scale / 1024) * size,
  }
}

// Convert a world-unit radius to canvas pixels
function worldRadiusToPx(r, bounds, size) {
  return (r / bounds.scale / 1024) * size
}

export function useMapCanvas() {
  const canvasRef = useRef(null)

  const redraw = useCallback((frames, frameIdx, bounds, mapImage, hiddenPlayers, playerColorMap, grenades) => {
    const canvas = canvasRef.current
    if (!canvas) return

    const size = canvas.parentElement?.clientWidth || 560
    canvas.width  = size
    canvas.height = size
    const ctx = canvas.getContext('2d')

    ctx.fillStyle = '#0a0a10'
    ctx.fillRect(0, 0, size, size)

    if (mapImage) {
      ctx.globalAlpha = 0.55
      ctx.drawImage(mapImage, 0, 0, size, size)
      ctx.globalAlpha = 1
    }

    if (!frames.length || !bounds) return
    const frame = frames[frameIdx]
    if (!frame) return

    // ── Grenades ──────────────────────────────────────────────
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
        ctx.lineWidth   = 1.5
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
      for (let i = 1; i < pts.length; i++) {
        if (!pts[i - 1].alive || !pts[i].alive) continue
        const ca = worldToCanvas(pts[i - 1].x, pts[i - 1].y, bounds, size)
        const cb = worldToCanvas(pts[i].x, pts[i].y, bounds, size)
        ctx.beginPath()
        ctx.strokeStyle = color
        ctx.globalAlpha = 0.12 + 0.55 * (i / pts.length)
        ctx.lineWidth   = 1.5
        ctx.moveTo(ca.x, ca.y)
        ctx.lineTo(cb.x, cb.y)
        ctx.stroke()
      }
    })
    ctx.globalAlpha = 1

    // ── Players ──────────────────────────────────────────────
    frame.p.forEach(pl => {
      if (hiddenPlayers.has(pl.n)) return
      const color = playerColorMap[pl.n] || '#fff'
      const pos   = worldToCanvas(pl.x, pl.y, bounds, size)
      const r     = 7

      if (!pl.alive) {
        ctx.strokeStyle = color
        ctx.globalAlpha = 0.35
        ctx.lineWidth   = 2
        ctx.beginPath(); ctx.moveTo(pos.x - 4, pos.y - 4); ctx.lineTo(pos.x + 4, pos.y + 4); ctx.stroke()
        ctx.beginPath(); ctx.moveTo(pos.x + 4, pos.y - 4); ctx.lineTo(pos.x - 4, pos.y + 4); ctx.stroke()
        ctx.globalAlpha = 1
        return
      }

      // HP arc
      ctx.beginPath()
      ctx.arc(pos.x, pos.y, r + 2, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * Math.min(1, (pl.hp || 0) / 100))
      ctx.strokeStyle = color
      ctx.lineWidth   = 2.5
      ctx.globalAlpha = 0.7
      ctx.stroke()

      // Fill dot
      ctx.beginPath()
      ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2)
      ctx.fillStyle   = color
      ctx.globalAlpha = 0.9
      ctx.fill()

      // Side ring (CT = blue, T = yellow)
      ctx.beginPath()
      ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2)
      ctx.strokeStyle = (pl.side || '').toUpperCase().includes('CT') ? '#38bdf8' : '#fbbf24'
      ctx.lineWidth   = 1.5
      ctx.globalAlpha = 1
      ctx.stroke()

      // Name label
      ctx.font      = 'bold 9px sans-serif'
      ctx.textAlign = 'center'
      ctx.fillStyle   = '#fff'
      ctx.globalAlpha = 0.9
      ctx.fillText(pl.n.split(' ')[0].substring(0, 8), pos.x, pos.y - r - 3)
      ctx.globalAlpha = 1
    })
  }, [])

  return { canvasRef, redraw }
}
