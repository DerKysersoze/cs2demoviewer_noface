import { useState } from 'react'
import WeaponIcon from '../../../components/WeaponIcon'
import styles from '../Viewer.module.css'

const WEAR_COLOR = {
  'Factory New':    '#4ade80',
  'Minimal Wear':   '#86efac',
  'Field-Tested':   '#fbbf24',
  'Well-Worn':      '#fb923c',
  'Battle-Scarred': '#f87171',
}

function WeaponRows({ weapons }) {
  if (!weapons.length) {
    return (
      <tr>
        <td colSpan={5} style={{ color: 'var(--muted)', fontSize: '.82rem' }}>
          No skinned weapons
        </td>
      </tr>
    )
  }
  return weapons.map((w, i) => {
    const tierColor = WEAR_COLOR[w.wear_tier] || 'var(--muted)'
    return (
      <tr key={i}>
        <td style={{ whiteSpace: 'nowrap' }}>
          <WeaponIcon weapon={w.item_name} catHint={w.weapon_cat} />
          {' '}
          <span style={{ fontSize: '.84rem' }}>
            {w.item_name}
            {w.custom_name && (
              <><br /><span style={{ color: 'var(--ct)', fontSize: '.72rem' }}>"{w.custom_name}"</span></>
            )}
          </span>
        </td>
        <td>
          {w.skin_name
            ? <span>{w.skin_name}</span>
            : <span className="muted">Vanilla</span>
          }
        </td>
        <td>
          {w.wear != null
            ? <><span style={{ color: tierColor }}>{w.wear_tier}</span><br />
                <span className="muted" style={{ fontSize: '.72rem' }}>{w.wear}</span></>
            : <span className="muted">—</span>
          }
        </td>
        <td className="r" style={{ color: 'var(--muted)', fontSize: '.8rem' }}>
          {w.paint_seed ?? '—'}
        </td>
        <td className="r">
          {w.stattrak != null
            ? <span style={{ color: '#e8a400', fontSize: '.78rem' }}>ST™ {w.stattrak.toLocaleString()}</span>
            : <span className="muted">—</span>
          }
        </td>
      </tr>
    )
  })
}

function SideCard({ label, color, agent, weapons }) {
  return (
    <div className={styles.aimCard} style={{ marginBottom: 14 }}>
      <div className={styles.swagSideLabel} style={{ color }}>{label}</div>
      {agent && (
        <div className={styles.agentRow}>
          <span className={styles.agentLabel}>Agent</span>
          <span style={{ fontSize: '.88rem' }}>{agent.item_name}</span>
        </div>
      )}
      <div className="table-wrap" style={{ border: 'none', borderRadius: 0, margin: 0 }}>
        <table>
          <thead>
            <tr>
              <th>Weapon</th>
              <th>Skin</th>
              <th>Wear</th>
              <th className="r">Seed</th>
              <th className="r">StatTrak</th>
            </tr>
          </thead>
          <tbody>
            <WeaponRows weapons={weapons} />
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function SwagBreakdown({ swagBreakdown }) {
  const [selectedIdx, setSelectedIdx] = useState(null)

  if (!swagBreakdown?.length) {
    return (
      <div className={styles.aimCard} style={{ color: 'var(--muted)' }}>
        No cosmetic data found in this demo.
      </div>
    )
  }

  const selected = selectedIdx !== null ? swagBreakdown[selectedIdx] : null

  return (
    <div className={styles.aimLayout}>
      <div className={styles.aimPlayerList}>
        {swagBreakdown.map((p, i) => {
          const side = p.team === 'CT' ? 'ct' : 't'
          return (
            <button
              key={p.name}
              className={`${styles.aimPlayerBtn}${selectedIdx === i ? ' ' + styles.active : ''}`}
              onClick={() => setSelectedIdx(i)}
            >
              <span className={`badge badge-${side}`} style={{ marginRight: 6, fontSize: '.6rem' }}>
                {p.team}
              </span>
              {p.name}
            </button>
          )
        })}
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        {!selected
          ? <div className={styles.aimCard} style={{ color: 'var(--muted)', fontSize: '.88rem' }}>
              Select a player to view their loadout.
            </div>
          : <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                <span className={`badge badge-${selected.team === 'CT' ? 'ct' : 't'}`}>
                  {selected.team}
                </span>
                <strong style={{ fontSize: '1rem' }}>
                  {selected.steamid
                    ? <a href={`https://steamcommunity.com/profiles/${selected.steamid}`}
                         target="_blank" rel="noopener noreferrer"
                         style={{ color: 'inherit', textDecoration: 'underline dotted' }}>
                        {selected.name}
                      </a>
                    : selected.name
                  }
                </strong>
              </div>
              <SideCard
                label="CT Side" color="var(--ct)"
                agent={selected.ct_agent} weapons={selected.ct_weapons}
              />
              <SideCard
                label="T Side" color="var(--t)"
                agent={selected.t_agent} weapons={selected.t_weapons}
              />
            </>
        }
      </div>
    </div>
  )
}
