/**
 * deriveOverview — match-level aggregates for the Overview tab.
 *
 * Everything here is derived on the frontend from the already-loaded
 * payload (scoreboard + aim_breakdown + kills + rounds) — no extra API
 * calls, no new parsing.
 *
 * Produces:
 *   teams        { CT: {...}, T: {...} } — at-a-glance aggregates per team
 *   flow         [{ num, winner, reason, halfBefore }] — one entry per round
 *   topName      the MVP (same rule as the Players tab: kills desc, then K/D)
 *   totalRounds  rounds played (the divisor for ADR = total DMG ÷ rounds)
 *   kastByName   { name: kast } — from aim_breakdown
 *   best         { kills, kd, kast, dmg, hs_pct } — best-of-match per column
 *                 (the player NAME holding each column's best value)
 */

const isCt = (t = '') => typeof t === 'string' && t.toUpperCase().includes('CT')
const realName = (n) => !!n && n !== '?' && n !== 'nan'

/** { name: kast } from the aim breakdown (skips unattributed entries). */
function kastByName(aimBreakdown) {
  const out = {}
  for (const a of aimBreakdown) {
    if (realName(a.name) && Number.isFinite(a.kast)) out[a.name] = a.kast
  }
  return out
}

/**
 * At-a-glance aggregates per team.
 * HS % is estimated as ΣHS-kills/Σkills where HS-kills ≈ round(K × hs_pct/100)
 * (the payload stores the rounded percentage, not raw HS counts).
 */
function teamAggregates({ scoreboard, aimBreakdown, wins }) {
  const team = (key) => scoreboard.filter((p) => (key === 'CT' ? isCt(p.team) : !isCt(p.team)))

  const build = (key) => {
    const members = team(key)

    const killsTot  = members.reduce((s, m) => s + (m.kills ?? 0), 0)
    const deathsTot = members.reduce((s, m) => s + (m.deaths ?? 0), 0)
    const assistsTot= members.reduce((s, m) => s + (m.assists ?? 0), 0)
    const dmgTot    = members.reduce((s, m) => s + (m.dmg ?? 0), 0)
    const hsEst     = members.reduce((s, m) => s + Math.round((m.kills ?? 0) * (m.hs_pct ?? 0) / 100), 0)

    // Team MVP: the side's best player — kills desc, then K/D desc
    // (the same rule as the match MVP badge in the stats table).
    const mvp = members.length
      ? [...members].sort(
          (a, b) => (b.kills ?? 0) - (a.kills ?? 0) || (b.kd ?? 0) - (a.kd ?? 0)
        )[0]
      : null

    // Team KAST: the members' average (rounded).
    const kasts = members
      .map((m) => aimBreakdown.find((a) => a.name === m.name)?.kast)
      .filter((v) => Number.isFinite(v))
    const kast = kasts.length
      ? Math.round(kasts.reduce((s, v) => s + v, 0) / kasts.length)
      : null

    return {
      key,
      winner:   key === (wins.CT > wins.T ? 'CT' : wins.T > wins.CT ? 'T' : null),
      wins:     wins[key] ?? 0,
      dmg:      dmgTot,
      hsPct:    killsTot ? Math.round(100 * hsEst / killsTot) : 0,
      kast,
      mvp: mvp ? { name: mvp.name, steamid: mvp.steamid || null } : null,
      killsTot,
      deathsTot,
      assistsTot,
    }
  }

  return { CT: build('CT'), T: build('T') }
}

/**
 * Round flow: winner + end reason per round, plus where the MR12 half break
 * falls (the half ends when a team reaches 8, or after 12 rounds of the
 * half — whichever first; the marker is drawn before the first round of
 * the second half).
 */
function roundFlow(rounds) {
  const flow = rounds.map((r) => ({
    num:      r.round_num,
    winner:   r.winner_side || null,
    reason:   r.reason || '',
    halfBefore: false,
  }))
  for (let i = 0; i < flow.length; i++) {
    const r = rounds[i]
    const scoreReached8 = (r.ct_score === 8) || (r.t_score === 8)
    const twelveRounds  = (i + 1) === 12
    if ((scoreReached8 || twelveRounds) && i < flow.length - 1) {
      flow[i + 1].halfBefore = true
      break
    }
  }
  return flow
}

/** MVP — same rule as the Players tab rail: kills desc, then K/D desc. */
function topPlayer(scoreboard) {
  if (!scoreboard.length) return null
  return [...scoreboard].sort((a, b) => b.kills - a.kills || b.kd - a.kd)[0]?.name || null
}

/** Best-of-match per column: the name holding each column's max value. */
function bestPerColumn(scoreboard, kastByName) {
  const best = {}
  const max = (key, valOf) => {
    let name = null, v = -Infinity
    for (const p of scoreboard) {
      const x = valOf(p)
      if (x > v) { v = x; name = p.name }
    }
    return name
  }
  best.kills   = max('kills',   (p) => p.kills ?? 0)
  best.kd      = max('kd',      (p) => (p.deaths > 0 ? p.kills / p.deaths : p.kills))
  best.dmg     = max('dmg',     (p) => p.dmg ?? 0)
  best.hs_pct  = max('hs_pct',  (p) => p.hs_pct ?? 0)
  best.kast    = max('kast',    (p) => (p.name in kastByName ? kastByName[p.name] : -1))
  return best
}

export default function deriveOverview({ scoreboard = [], aimBreakdown = [], rounds = [] }) {
  const wins = { CT: 0, T: 0 }
  for (const r of rounds) {
    if (r.winner_side === 'CT') wins.CT += 1
    else if (r.winner_side === 'T') wins.T += 1
  }
  const kast = kastByName(aimBreakdown)
  return {
    teams:        teamAggregates({ scoreboard, aimBreakdown, wins }),
    flow:         roundFlow(rounds),
    topName:      topPlayer(scoreboard),
    totalRounds:  rounds.length,
    kastByName:   kast,
    best:         bestPerColumn(scoreboard, kast),
  }
}
