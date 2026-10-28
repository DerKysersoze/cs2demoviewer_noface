/**
 * deriveHighlights — auto-detected moments from the already-loaded payload
 * (rounds + kills + scoreboard). No extra API calls, frontend-only.
 *
 * Types (matching the reference list):
 *   multi-kill 🔥  2+ kills by one player within a 3 s window (Ace = 5)
 *   streak     📈  3+ kills by one player in a round, spread out (not a
 *                  multi-kill window) — slow pick-off rounds
 *   clutch     🎯  elimination round closed by a player with 3+ kills in it
 *   top-damage ⚡  scoreboard leaders (match-wide, not tied to a round)
 *   bomb       💣  round ended by bomb explosion
 *   defuse     🛠  round ended by bomb defuse
 *
 * Each entry: { type, title, detail, round (nullable), timeSec (round-relative) }
 * Entries about a specific player also carry
 *   player: { name, steamid (nullable), in: 'title' | 'detail' }
 * with the player's name removed from the title/detail text (the UI renders
 * the name as a Steam community profile link before the remaining text).
 */

const WINDOW_S = 3  // max span for a multi-kill window

export default function deriveHighlights({ rounds = [], kills = [], scoreboard = [], tickrate = 128 }) {
  const tr = tickrate || 128
  const out = []

  // name -> SteamID64 (scoreboard is the reliable id source; kills carry names only)
  const sidOf = new Map()
  for (const s of scoreboard) if (s.name && s.steamid) sidOf.set(s.name, s.steamid)
  const playerFor = (name) => ({ name, steamid: sidOf.get(name) || null })

  const byRound = new Map()
  for (const k of kills) {
    if (!k.round_num) continue
    if (!byRound.has(k.round_num)) byRound.set(k.round_num, [])
    byRound.get(k.round_num).push(k)
  }

  const roundStart = new Map(rounds.map((r) => [r.round_num, r.start_tick]))
  const roundEnd   = new Map(rounds.map((r) => [r.round_num, r.end_tick]))

  // Seconds of a tick within its round (null when the round has no start tick).
  const tSec = (rnum, tick) => {
    const s0 = roundStart.get(rnum)
    return s0 != null && tick != null ? (tick - s0) / tr : null
  }

  const realKill = (k) => k.attacker && k.attacker !== '?' && k.attacker !== k.victim

  for (const r of rounds) {
    const list = (byRound.get(r.round_num) || []).filter(realKill)
    if (!list.length) continue
    // The round's final kill (used by the clutch check below)
    const roundLast = list.reduce((a, b) => (b.tick > a.tick ? b : a))
    const byAtt = new Map()
    for (const k of list) {
      if (!byAtt.has(k.attacker)) byAtt.set(k.attacker, [])
      byAtt.get(k.attacker).push(k)
    }

    for (const [name, ks] of byAtt) {
      const sorted = [...ks].sort((a, b) => a.tick - b.tick)

      // Densest kill window (multi-kill / ace)
      let bestN = 1
      let bestAt = sorted[0].tick
      const winTicks = WINDOW_S * tr
      for (let i = 0; i < sorted.length; i++) {
        let j = i
        while (j + 1 < sorted.length && sorted[j + 1].tick - sorted[i].tick <= winTicks) j++
        if (j - i + 1 > bestN) {
          bestN = j - i + 1
          bestAt = sorted[i].tick
        }
      }

      if (bestN >= 2) {
        const label =
          bestN === 2 ? 'Double kill' :
          bestN === 3 ? 'Triple kill' :
          bestN === 4 ? 'Quad kill' :
          bestN === 5 ? 'Ace' :
          `${bestN}-kill spree`
        out.push({
          type:   'multi-kill',
          title:  label,
          detail: `— round ${r.round_num}`,
          player: { ...playerFor(name), in: 'detail' },
          round:  r.round_num,
          timeSec: tSec(r.round_num, bestAt),
          count:  bestN, // kills inside the window (UI shorthand: double/triple/…)
        })
      } else if (ks.length >= 3) {
        // 3+ kills, none within 3 s of each other — a sustained pick-off
        out.push({
          type:   'streak',
          title:  `on a ${ks.length}-kill run`,
          detail: `round ${r.round_num}`,
          player: { ...playerFor(name), in: 'title' },
          round:  r.round_num,
          timeSec: tSec(r.round_num, sorted[0].tick),
          count:  ks.length, // kills in the round (UI shorthand: 3-kill run)
        })
      }

      // Clutch: elimination round whose FINAL kill was taken by this player,
      // and they had 3+ kills in the round.
      if (r.reason === 'Ct Killed' || r.reason === 'T Killed') {
        if (roundLast.attacker === name && ks.length >= 3) {
          out.push({
            type:   'clutch',
            title:  'Clutch',
            detail: `closed round ${r.round_num} with ${ks.length} kills`,
            player: { ...playerFor(name), in: 'detail' },
            round:  r.round_num,
            timeSec: tSec(r.round_num, roundLast.tick),
            count:  ks.length, // kills in the round (UI shorthand: 4K)
          })
        }
      }
    }

    // Bomb / defuse endings (round-level, timestamped at the round's end tick)
    const endSec = tSec(r.round_num, roundEnd.get(r.round_num))
    if (r.reason === 'Bomb Exploded') {
      out.push({
        type:   'bomb',
        title:  'Bomb exploded',
        detail: `round ${r.round_num}`,
        round:  r.round_num,
        timeSec: endSec,
        winner: 'T', // the round went to T (UI shorthand: “T took it”)
      })
    }
    if (r.reason === 'Bomb Defused') {
      out.push({
        type:   'defuse',
        title:  'Bomb defused',
        detail: `round ${r.round_num}`,
        round:  r.round_num,
        timeSec: endSec,
        winner: 'CT', // the round went to CT (UI shorthand: “CT took it”)
      })
    }
  }

  // Top damage — match-wide, not tied to a round (informational)
  const top = [...scoreboard]
    .filter((s) => (s.dmg ?? 0) > 0)
    .sort((a, b) => (b.dmg ?? 0) - (a.dmg ?? 0))
    .slice(0, 3)
  for (const s of top) {
    out.push({
      type:   'top-damage',
      title:  'Top damage',
      detail: `— ${s.dmg} dmg`,
      player: { ...playerFor(s.name), in: 'detail' },
      round:  null,
      timeSec: null,
    })
  }

  // Stable order: round events first (by round, then time), match-wide last
  out.sort((a, b) => {
    if (a.round == null && b.round == null) return 0
    if (a.round == null) return 1
    if (b.round == null) return -1
    if (a.round !== b.round) return a.round - b.round
    return (a.timeSec ?? 0) - (b.timeSec ?? 0)
  })

  return out
}
