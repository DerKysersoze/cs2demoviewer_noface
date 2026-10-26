/**
 * Assign a player altitude (z) to a floor section (HLTV overview ranges).
 * Players without z (demos parsed before z was stored) fall back to the
 * default floor. Out-of-range z goes to the nearest section.
 *
 * Used by MapReplayStage (per-frame floor visibility) and the Results band
 * header (per-floor player counts) — kept component-free for fast-refresh.
 */
export function floorForZ(z, floors, fallback) {
  if (z == null) return fallback
  for (const f of floors) {
    if (z >= f.alt_min && z < f.alt_max) return f.name
  }
  let best = null
  let bestD = Infinity
  for (const f of floors) {
    const d = z < f.alt_min ? f.alt_min - z : Math.max(0, z - f.alt_max)
    if (d < bestD) { bestD = d; best = f }
  }
  return best ? best.name : fallback
}
