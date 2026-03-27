import { useState, useRef } from 'react'
import styles from '../Viewer.module.css'

const REASON_ICON = {
  'Bomb Defused':             '🔵',
  'Bomb Exploded':            '💥',
  'Target Bombed':            '💥',
  'Ct Win':                   '🛡',
  'Counter Terrorists Win':   '🛡',
  'T Win':                    '💣',
  'Terrorists Win':           '💣',
  'Target Saved':             '⏱',
}

function reasonIcon(reason) {
  for (const [k, v] of Object.entries(REASON_ICON))
    if (reason.toLowerCase().includes(k.toLowerCase())) return v
  return '🎯'
}

function groupIntoHalves(rounds) {
  const halves = []
  rounds.forEach(r => {
    const hi = r.round_num <= 12 ? 0
             : r.round_num <= 24 ? 1
             : 2 + Math.floor((r.round_num - 25) / 6)
    if (!halves[hi]) halves[hi] = []
    halves[hi].push(r)
  })
  return halves
}

export default function Timeline({ rounds, kills, ctTeam, tTeam }) {
  const [selectedRound, setSelectedRound] = useState(null)
  const detailRef = useRef(null)

  const halves = groupIntoHalves(rounds)
  const halfLabels = ['1st Half', '2nd Half']

  function handleBlockClick(roundNum) {
    if (selectedRound === roundNum) {
      setSelectedRound(null)
      return
    }
    setSelectedRound(roundNum)
    requestAnimationFrame(() =>
      detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    )
  }

  const selectedRoundData = rounds.find(r => r.round_num === selectedRound)
  const selectedKills     = kills.filter(k => k.round_num === selectedRound)

  return (
    <>
      {halves.map((group, idx) => {
        if (!group) return null
        const label = halfLabels[idx] || `Overtime ${idx - 1}`
        const ctW   = group.filter(r => r.winner_side === 'CT').length
        const tW    = group.length - ctW

        return (
          <div key={idx} className={styles.timelineHalf}>
            <div className={styles.timelineHalfLabel}>
              {label}&nbsp;&nbsp;
              <span className={styles.ctColor}>{ctTeam} {ctW}</span>
              <span className="muted"> – </span>
              <span className={styles.tColor}>{tW} {tTeam}</span>
            </div>
            <div className={styles.timelineRow}>
              {group.map(r => {
                const isCt   = r.winner_side === 'CT'
                const active = selectedRound === r.round_num
                return (
                  <div
                    key={r.round_num}
                    className={[
                      styles.roundBlock,
                      isCt ? styles.roundBlockCt : styles.roundBlockT,
                      active ? styles.roundBlockActive : '',
                    ].join(' ')}
                    data-tip={r.reason}
                    onClick={() => handleBlockClick(r.round_num)}
                  >
                    <span className={styles.rnum}>{r.round_num}</span>
                    <span className={styles.ricon}>{reasonIcon(r.reason)}</span>
                    <span className={`${styles.rscore} ${isCt ? styles.rscoreCt : styles.rscoreT}`}>
                      {r.ct_score}:{r.t_score}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        )
      })}

      {selectedRound && selectedRoundData && (
        <div className={styles.roundDetail} ref={detailRef}>
          <div className={styles.roundDetailHeader}>
            <span style={{ fontSize: '1.1rem' }}>
              {reasonIcon(selectedRoundData.reason)}
            </span>
            <span>Round {selectedRoundData.round_num}</span>
            <span className={`badge ${selectedRoundData.winner_side === 'CT' ? 'badge-ct' : 'badge-t'}`}>
              {selectedRoundData.winner_side} Win
            </span>
            <span className="muted" style={{ fontWeight: 400 }}>{selectedRoundData.reason}</span>
            <span className="muted" style={{ marginLeft: 'auto', fontWeight: 400, fontSize: '.8rem' }}>
              {selectedKills.length} kills
            </span>
          </div>

          {selectedKills.length === 0 ? (
            <div className={styles.roundKillRow} style={{ color: 'var(--muted)' }}>
              No kill data for this round.
            </div>
          ) : (
            selectedKills.map((k, i) => (
              <div key={i} className={styles.roundKillRow}>
                <span className={`${styles.rkAttacker} ${styles.ctColor}`}>{k.attacker}</span>
                <span className={styles.rkArrow}>›</span>
                <span className={styles.rkWeapon}>{k.weapon}</span>
                <span className={styles.rkArrow}>›</span>
                <span className={styles.rkVictim}>{k.victim}</span>
                <span className={styles.rkBadges}>
                  {k.headshot      && <span className="badge" style={{ background:'rgba(250,204,21,.15)', color:'#facc15' }}>HS</span>}
                  {k.through_smoke && <span className="badge badge-note">smoke</span>}
                  {k.no_scope      && <span className="badge badge-note">no-scope</span>}
                  {k.penetrated    && <span className="badge badge-note">wall</span>}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </>
  )
}
