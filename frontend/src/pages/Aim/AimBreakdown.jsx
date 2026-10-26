import { useState } from 'react'
import SortableTable from '../../components/SortableTable'
import WeaponIcon from '../../components/WeaponIcon'
import styles from './AimBreakdown.module.css'

const HG_ORDER = ['Head','Neck','Chest','Stomach','L Arm','R Arm','L Leg','R Leg','Gear','Generic']
const HG_COLORS = {
  Head: '#f87171', Neck: '#fb923c', Chest: '#60a5fa', Stomach: '#a78bfa',
  'L Arm': '#34d399', 'R Arm': '#34d399', 'L Leg': '#fbbf24', 'R Leg': '#fbbf24',
  Gear: '#94a3b8', Generic: '#6b7280',
}

const WPN_COLS = [
  { key: 'weapon',   label: 'Weapon',   render: (v) => <WeaponIcon weapon={v} /> },
  { key: 'shots',    label: 'Shots',    className: 'r', render: v => v ?? '—' },
  { key: 'hits',     label: 'Hits',     className: 'r' },
  { key: 'acc',      label: 'Acc %',    className: 'r', render: v => v != null ? `${v}%` : '—' },
  { key: 'dmg',      label: 'Dmg',      className: 'r', render: v => v.toLocaleString() },
  { key: 'avgDmg',   label: 'Avg Dmg',  className: 'r', render: v => v.toLocaleString() },
  { key: 'kills',    label: 'Kills',    className: 'r' },
  { key: 'hs_kills', label: 'HS Kills', className: 'r', render: v => <span style={{ color: 'rgb(var(--red))' }}>{v}</span> },
]

function Stat({ value, label, color, tip }) {
  return (
    <div className={styles.aimStat} data-tip={tip}>
      <span className={styles.aimStatVal} style={color ? { color } : undefined}>{value}</span>
      <span className={styles.aimStatLbl}>{label}</span>
    </div>
  )
}

function AimDetail({ p }) {
  const th = p.total_hits

  const wpnRows = p.weapons.map(w => ({
    weapon:   w.weapon,
    shots:    w.shots ?? null,
    hits:     w.hits,
    acc:      (w.shots && w.hits) ? Math.min(100, Math.round(100 * w.hits / w.shots)) : null,
    dmg:      w.dmg,
    avgDmg:   w.hits ? Math.round(w.dmg / w.hits) : 0,
    kills:    w.kills,
    hs_kills: w.hs_kills,
  }))

  return (
    <div className={styles.aimDetail}>
      {/* Summary stats */}
      <div className={styles.aimCard}>
        <h4>Summary — {p.name}</h4>
        <div className={styles.aimStatsRow}>
          <Stat value={p.total_hits}             label="Total Hits"       tip="Every bullet or grenade hit\nregistered on an enemy,\nexcluding self-damage." />
          <Stat value={p.total_dmg.toLocaleString()} label="Total Damage" tip="Sum of all hp damage dealt\nto enemies across the match\n(capped at target's remaining hp)." />
          <Stat value={p.avg_dmg}                label="Avg Dmg / Hit"    tip="Total damage ÷ total hits.\nHigher = better shot selection\nor use of high-damage weapons." />
          <Stat value={`${p.hs_hit_pct}%`}       label="Headshot Hit %"  color="rgb(var(--red))"   tip="% of all hits that landed\non the head hitbox.\nDoes not require a kill." />
          <Stat value={`${p.kast}%`}             label="KAST"             color="rgb(var(--green))" tip="Kill / Assist / Survived / Traded.\n% of rounds where the player\ngot a kill, assist, survived,\nor was traded within 5 s.\nGood players typically 70%+." />
          <Stat value={p.total_shots ?? '—'}     label="Total Shots"      tip="Total bullets fired (grenades\nexcluded). Counted from the\nshots event in the demo file." />
          {p.accuracy != null && (
            <Stat value={`${p.accuracy}%`} label="Accuracy" color="rgb(var(--ct))" tip="Total hits ÷ total shots × 100.\nOnly bullet weapons counted;\ngrenades are excluded." />
          )}
        </div>
      </div>

      {/* Hit location breakdown */}
      <div className={styles.aimCard}>
        <h4 data-tip="Where each bullet landed on\nthe enemy's body. Bar width =\n% of total hits on that zone.\nCount shows raw number of hits.">
          Hit Location Breakdown
        </h4>
        {HG_ORDER.filter(hg => p.hit_groups[hg]).map(hg => {
          const count = p.hit_groups[hg] || 0
          const pct   = th ? Math.round(100 * count / th) : 0
          return (
            <div key={hg} className={styles.hgRow}>
              <span className={styles.hgLabel}>{hg}</span>
              <div className={styles.hgBarBg}>
                <div
                  className={styles.hgBarFill}
                  style={{ width: `${pct}%`, background: HG_COLORS[hg] || '#6b7280' }}
                />
              </div>
              <span className={styles.hgCount}>{count}</span>
              <span className={styles.hgPct} style={{ color: HG_COLORS[hg] || '#6b7280' }}>{pct}%</span>
            </div>
          )
        })}
        {!HG_ORDER.some(hg => p.hit_groups[hg]) && (
          <span className="muted">No data</span>
        )}
      </div>

      {/* Per-weapon sortable table */}
      <div className={styles.aimCard} style={{ padding: 0, overflow: 'hidden' }}>
        <h4 style={{ padding: '14px 16px 10px' }}>Per-Weapon Stats</h4>
        <div style={{ borderTop: '1px solid var(--border)' }}>
          <SortableTable columns={WPN_COLS} rows={wpnRows} defaultSort="kills" />
        </div>
      </div>
    </div>
  )
}

/**
 * AimBreakdown — per-player aim breakdown, shared by the standalone
 * `/aim/<demoId>` page and the Results page's **Aim** tab:
 * player list + summary stats, hit-location bars and the per-weapon table.
 */
export default function AimBreakdown({ aimBreakdown }) {
  const [selectedIdx, setSelectedIdx] = useState(0)

  if (!aimBreakdown?.length) {
    return <div className={styles.aimCard} style={{ color: 'var(--muted)' }}>No aim data in this demo.</div>
  }

  return (
    <div className={styles.aimLayout}>
      <div className={styles.aimPlayerList}>
        {aimBreakdown.map((p, i) => (
          <button
            key={p.name}
            type="button"
            className={`${styles.aimPlayerBtn}${selectedIdx === i ? ' ' + styles.active : ''}`}
            onClick={() => setSelectedIdx(i)}
          >
            {p.name}
          </button>
        ))}
      </div>

      <div>
        {selectedIdx === null
          ? <div className={styles.aimCard} style={{ color: 'var(--muted)', fontSize: '.88rem' }}>
              Select a player to view their aim breakdown.
            </div>
          : <AimDetail p={aimBreakdown[selectedIdx]} />}
      </div>
    </div>
  )
}
