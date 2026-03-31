import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { demosApi } from '../../api/demos'
import SiteHeader from '../../components/SiteHeader'
import WeaponIcon from '../../components/WeaponIcon'
import styles from './Loadout.module.css'

const WEAR_COLOR = {
  'Factory New':    '#4ade80',
  'Minimal Wear':   '#86efac',
  'Field-Tested':   '#fbbf24',
  'Well-Worn':      '#fb923c',
  'Battle-Scarred': '#f87171',
}

function PlayerCard({ player, activeTab }) {
  const playerTeam = player.team || 'Unknown'

  return (
    <div className={styles.playerCard}>
      <div className={styles.playerHeader}>
        <h3 className={styles.playerName}>{player.name || 'Unknown Player'}</h3>
        <span className={`${styles.teamBadge} ${playerTeam === 'CT' ? styles.ct : styles.t}`}>
          {playerTeam}
        </span>
      </div>

      <div className={styles.statsGrid}>
        <div className={styles.statCard}>
          <div className={styles.statValue}>{player.kills ?? 0}</div>
          <div className={styles.statLabel}>Kills</div>
        </div>
        <div className={styles.statCard}>
          <div className={styles.statValue}>{player.deaths ?? 0}</div>
          <div className={styles.statLabel}>Deaths</div>
        </div>
        <div className={styles.statCard}>
          <div className={styles.statValue}>{player.assists ?? 0}</div>
          <div className={styles.statLabel}>Assists</div>
        </div>
        <div className={styles.statCard}>
          <div className={styles.statValue}>{player.kd_ratio ?? '0.00'}</div>
          <div className={styles.statLabel}>K/D</div>
        </div>
        <div className={styles.statCard}>
          <div className={styles.statValue}>{player.headshot_pct ?? 0}%</div>
          <div className={styles.statLabel}>HS%</div>
        </div>
        <div className={styles.statCard}>
          <div className={styles.statValue}>{player.total_damage ?? 0}</div>
          <div className={styles.statLabel}>Damage</div>
        </div>
      </div>

      {activeTab === 'weapons' && (
        <div className={styles.weaponsGrid}>
          {player.weapons && player.weapons.length > 0 ? (
            player.weapons.map((weapon, i) => (
              <div key={i} className={styles.weaponCard}>
                <div className={styles.weaponImage}>
                  <WeaponIcon weapon={weapon.weapon} />
                </div>
                <div className={styles.weaponName}>{weapon.weapon}</div>
                <div className={styles.weaponStats}>
                  <span>Kills: {weapon.kills}</span>
                  <span>HS Kills: {weapon.hs_kills}</span>
                  <span>Shots: {weapon.shots}</span>
                  <span>Hits: {weapon.hits}</span>
                  <span>Dmg: {weapon.dmg}</span>
                </div>
              </div>
            ))
          ) : (
            <div className={styles.noData}>No weapon data</div>
          )}
        </div>
      )}

      {activeTab === 'agent' && (
        <div className={styles.agentSection}>
          {player.agent ? (
            <div className={styles.agentCard}>
              <div className={styles.agentImage}>
                <span className={styles.placeholderImage}>👤</span>
              </div>
              <div className={styles.agentName}>{player.agent.item_name}</div>
              {player.agent.skin_name && (
                <div className={styles.agentType}>{player.agent.skin_name}</div>
              )}
              <div className={styles.agentType}>
                {player.agent.side === 'ct' ? 'CT' : player.agent.side === 't' ? 'T' : 'Both sides'}
              </div>
            </div>
          ) : (
            <div className={styles.noData}>No agent equipped</div>
          )}
        </div>
      )}

      {activeTab === 'skins' && (
        <div className={styles.skinsGrid}>
          {player.skins && player.skins.length > 0 ? (
            player.skins.map((skin, i) => {
              const tierColor = WEAR_COLOR[skin.wear_tier] || 'var(--muted)'
              return (
                <div key={i} className={styles.skinCard}>
                  <div className={styles.skinImage}>
                    <WeaponIcon weapon={skin.item_name} />
                  </div>
                  <div className={styles.skinItemName}>
                    {skin.item_name}
                    {skin.stattrak && <span className={styles.stattrak}> ST</span>}
                  </div>
                  <div className={styles.skinName}>
                    {skin.skin_name || <span className={styles.vanilla}>Vanilla</span>}
                  </div>
                  {skin.custom_name && (
                    <div className={styles.customName}>"{skin.custom_name}"</div>
                  )}
                  {skin.wear_tier && (
                    <div className={styles.wearTier} style={{ color: tierColor }}>
                      {skin.wear_tier}
                      {skin.wear != null && (
                        <span className={styles.wearValue}> {skin.wear}</span>
                      )}
                    </div>
                  )}
                </div>
              )
            })
          ) : (
            <div className={styles.noData}>No skins equipped</div>
          )}
        </div>
      )}
    </div>
  )
}

export default function Loadout() {
  const { demoId } = useParams()
  const [activeTab, setActiveTab] = useState('weapons')

  const { data, isLoading, error } = useQuery({
    queryKey: ['demo-loadout', demoId],
    queryFn:  () => demosApi.getLoadout(demoId),
    enabled:  !!demoId,
  })

  if (isLoading) return (
    <div className={styles.container}>
      <SiteHeader />
      <div className={styles.loading}>Loading loadout data…</div>
    </div>
  )

  if (error) return (
    <div className={styles.container}>
      <SiteHeader />
      <div className={styles.error}>Error loading loadout: {error.message}</div>
    </div>
  )

  if (!data) return (
    <div className={styles.container}>
      <SiteHeader />
      <div className={styles.error}>No loadout data available</div>
    </div>
  )

  const players = data.players || []

  return (
    <div className={styles.container}>
      <SiteHeader />
      <div className={styles.header}>
        <h1>Loadout — {data.filename}</h1>
        <p>Map: {data.map}</p>
        <Link to={`/viewer/${demoId}`} className={styles.backButton}>
          ← Back to Demo Viewer
        </Link>
      </div>

      <div className={styles.content}>
        <div className={styles.tabs}>
          {['weapons', 'agent', 'skins'].map(tab => (
            <button
              key={tab}
              className={`${styles.tabButton} ${activeTab === tab ? styles.active : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        {players.length > 0 ? (
          players.map((player, i) => (
            <PlayerCard key={player.steamid || player.name || i} player={player} activeTab={activeTab} />
          ))
        ) : (
          <div className={styles.noPlayers}>No player data available</div>
        )}
      </div>
    </div>
  )
}
