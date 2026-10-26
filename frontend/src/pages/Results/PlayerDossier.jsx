import { useMemo, useState } from 'react'
import SortableTable from '../../components/SortableTable'
import WeaponIcon from '../../components/WeaponIcon'
import PlayerLink from './PlayerLink'
import styles from './Results.module.css'

const HG_ORDER = ['Head','Neck','Chest','Stomach','L Arm','R Arm','L Leg','R Leg','Gear','Generic']
const HG_COLORS = {
  Head: '#f87171', Neck: '#fb923c', Chest: '#60a5fa', Stomach: '#a78bfa',
  'L Arm': '#34d399', 'R Arm': '#34d399', 'L Leg': '#fbbf24', 'R Leg': '#fbbf24',
  Gear: '#94a3b8', Generic: '#6b7280',
}

const WPN_COLS = [
  { key: 'weapon', label: 'Weapon',  render: (v) => <WeaponIcon weapon={v} /> },
  { key: 'shots',  label: 'Shots',   className: 'r', render: v => v ?? '—' },
  { key: 'hits',   label: 'Hits',    className: 'r' },
  { key: 'acc',    label: 'Acc %',   className: 'r', render: v => v != null ? `${v}%` : '—' },
  { key: 'dmg',    label: 'DMG',     className: 'r', render: v => (v || 0).toLocaleString() },
  { key: 'kills',  label: 'Kills',   className: 'r' },
]

function Stat({ value, label, color }) {
  return (
    <div className={styles.statCell}>
      <span className={styles.statVal} style={color ? { color } : undefined}>{value}</span>
      <span className={styles.statLbl}>{label}</span>
    </div>
  )
}

const isCt = (t = '') => typeof t === 'string' && t.toUpperCase().includes('CT')

/**
 * PlayerDossier — the Results page's **Players** tab: a CT/T team rail that
 * doubles as navigation; picking a player shows their full stat set in one
 * place — match stats (K/D/A, K/D, DMG, HS%), aim summary (accuracy, KAST,
 * shots, hits, avg dmg, HS-hit %), the hit-location breakdown and the
 * per-weapon table.
 *
 * The rail rows are plain <button>s (names without links — an anchor inside
 * a button is invalid HTML); the dossier head name uses PlayerLink for the
 * Steam community profile.
 */
export default function PlayerDossier({ scoreboard = [], aimBreakdown = [] }) {
  const topName = useMemo(() => {
    if (!scoreboard.length) return null
    return [...scoreboard].sort((a, b) => b.kills - a.kills || b.kd - a.kd)[0]?.name || null
  }, [scoreboard])

  const [name, setName] = useState(null)
  const active = name || topName || scoreboard[0]?.name

  const sb  = scoreboard.find((p) => p.name === active) || null
  const aim = aimBreakdown.find((p) => p.name === active) || null

  const groups = useMemo(() => {
    const g = { CT: [], T: [] }
    for (const p of scoreboard) (isCt(p.team) ? g.CT : g.T).push(p)
    g.CT.sort((a, b) => b.kills - a.kills)
    g.T.sort((a, b) => b.kills - a.kills)
    return g
  }, [scoreboard])

  if (!scoreboard.length) {
    return <p className={styles.metaLine}>No scoreboard data in this demo.</p>
  }

  const th = aim?.total_hits || 0
  const bars = aim
    ? HG_ORDER.filter((hg) => aim.hit_groups?.[hg]).map((hg) => {
        const count = aim.hit_groups[hg] || 0
        const pct = th ? Math.round(100 * count / th) : 0
        return (
          <div key={hg} className={styles.hgRow}>
            <span className={styles.hgLabel}>{hg}</span>
            <div className={styles.hgBarBg}>
              <div className={styles.hgBarFill} style={{ width: `${pct}%`, background: HG_COLORS[hg] || '#6b7280' }} />
            </div>
            <span className={styles.hgCount}>{count}</span>
            <span className={styles.hgPct} style={{ color: HG_COLORS[hg] || '#6b7280' }}>{pct}%</span>
          </div>
        )
      })
    : null

  const wpnRows = aim
    ? aim.weapons.map((w) => ({
        weapon:  w.weapon,
        shots:   w.shots ?? null,
        hits:    w.hits,
        acc:     w.shots && w.hits ? Math.min(100, Math.round(100 * w.hits / w.shots)) : null,
        dmg:     w.dmg,
        kills:   w.kills,
      }))
    : []

  const railCol = (team, label) => (
    <div className={styles.railCol}>
      <div className={styles.railHead}>
        <span className={`${styles.teamDot} ${team === 'CT' ? styles.dotSolid : styles.dotOutline}`} aria-hidden="true" />
        {label}
      </div>
      {groups[team].map((p) => (
        <button
          key={p.name}
          type="button"
          className={`${styles.railBtn}${p.name === active ? ' ' + styles.railBtnOn : ''}`}
          onClick={() => setName(p.name)}
          aria-pressed={p.name === active}
        >
          <span>{p.name}</span>
          <span className={styles.railKd}>
            K/D {p.deaths ? (p.kills / p.deaths).toFixed(2) : p.kills} · {p.dmg.toLocaleString()} DMG · {p.hs_pct}% HS
          </span>
          <span className={styles.railKills}>{p.kills}</span>
        </button>
      ))}
    </div>
  )

  return (
    <div>
      <div className={styles.rail}>
        {railCol('CT', 'Counter-Terrorists')}
        {railCol('T', 'Terrorists')}
      </div>

      {sb && (
        <div className={styles.dossier}>
          <div className={styles.dossierCol}>
            <div className={styles.dossierCard}>
              <div className={styles.dossierName}>
                <span className={`${styles.teamDot} ${isCt(sb.team) ? styles.dotSolid : styles.dotOutline}`} aria-hidden="true" />
                <span className={styles.dossierNm}>
                  <PlayerLink name={sb.name} steamid={sb.steamid} className="link-underline" />
                </span>
                <span className={`${styles.dossierSide} ${isCt(sb.team) ? styles.sideCt : styles.sideT}`}>
                  {sb.team}
                </span>
                {sb.name === topName && <span className={styles.mvpBadge}>TOP PERFORMER</span>}
              </div>

              <div className={styles.dossierBody}>
                <h4 className={styles.cardH4}>Match stats</h4>
                <div className={styles.statGrid}>
                  <Stat value={sb.kills}   label="Kills" />
                  <Stat value={sb.deaths}  label="Deaths" />
                  <Stat value={sb.assists} label="Assists" />
                  <Stat value={sb.deaths ? (sb.kills / sb.deaths).toFixed(2) : sb.kills} label="K/D" />
                  <Stat value={sb.dmg.toLocaleString()} label="DMG" />
                  <Stat value={`${sb.hs_pct}%`} label="HS%" />
                </div>

                <h4 className={styles.cardH4}>Aim summary</h4>
                {aim ? (
                  <div className={styles.statGrid}>
                    <Stat value={`${aim.accuracy}%`} label="Accuracy" color="rgb(var(--ct))" />
                    <Stat value={`${aim.kast}%`}     label="KAST"     color="rgb(var(--green))" />
                    <Stat value={aim.total_shots ?? '—'} label="Shots" />
                    <Stat value={aim.total_hits}   label="Hits" />
                    <Stat value={aim.avg_dmg}      label="Avg Dmg/Hit" />
                    <Stat value={`${aim.hs_hit_pct}%`} label="HS Hit %" color="rgb(var(--red))" />
                  </div>
                ) : (
                  <p className={styles.metaLine} style={{ marginBottom: 14 }}>No aim data for this player.</p>
                )}
              </div>
            </div>

            <div className={styles.dossierCard}>
              <div className={styles.dossierBody}>
                <h4 className={styles.cardH4}>Hit location breakdown</h4>
                {bars || <span className="muted">No data</span>}
              </div>
            </div>
          </div>

          <div className={styles.dossierCol}>
            <div className={styles.dossierCard} style={{ padding: 0, overflow: 'hidden' }}>
              <h4 className={styles.cardH4} style={{ padding: '14px 16px 10px' }}>
                Per-weapon stats{aim ? ` — ${wpnRows.length} weapons` : ''}
              </h4>
              {aim ? (
                <SortableTable columns={WPN_COLS} rows={wpnRows} defaultSort="kills" />
              ) : (
                <p className="muted" style={{ padding: '0 16px 14px' }}>No aim data for this player.</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
