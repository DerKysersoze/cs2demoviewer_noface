import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { demosApi } from '../../api/demos'
import SiteHeader from '../../components/SiteHeader'
import WeaponIcon from '../../components/WeaponIcon'
import styles from './Loadout.module.css'

function AgentImage({ defIndex, name }) {
  const [errored, setErrored] = useState(false)
  if (defIndex && !errored) {
    return (
      <img
        src={`/images/agents/agent-${defIndex}.png`}
        alt={name}
        className={styles.agentImageImg}
        onError={() => setErrored(true)}
      />
    )
  }
  return <span className={styles.placeholderImage}>👤</span>
}

function SkinImage({ skin }) {
  const [errored, setErrored] = useState(false)
  if (skin.skin_image_id && !errored) {
    return (
      <img
        src={`/images/skins/${skin.skin_image_id}.png`}
        alt={skin.skin_name || skin.item_name}
        className={styles.skinImageImg}
        onError={() => setErrored(true)}
      />
    )
  }
  return <WeaponIcon weapon={skin.item_name} />
}

const WEAR_COLOR = {
  'Factory New':    '#4ade80',
  'Minimal Wear':   '#86efac',
  'Field-Tested':   '#fbbf24',
  'Well-Worn':      '#fb923c',
  'Battle-Scarred': '#f87171',
}

function PlayerCard({ player }) {
  const playerTeam = player.team || 'CT'
  const [activeSide, setActiveSide] = useState(playerTeam)

  const visibleSkins = (player.skins || []).filter(
    s => s.side === activeSide || s.side === 'both'
  )

  const agentForSide = player.agent && (
    player.agent.side === activeSide || player.agent.side === 'both'
  ) ? player.agent : null

  return (
    <div className={styles.playerCard}>
      <div className={styles.playerHeader}>
        <h3 className={styles.playerName}>{player.name || 'Unknown Player'}</h3>
        <span className={`${styles.teamBadge} ${playerTeam === 'CT' ? styles.ct : styles.t}`}>
          {playerTeam}
        </span>
        <div className={styles.sideToggle}>
          {['T', 'CT'].map(side => (
            <button
              key={side}
              className={`${styles.sideBtn} ${activeSide === side ? (side === 'CT' ? styles.activeCT : styles.activeT) : ''}`}
              onClick={() => setActiveSide(side)}
            >
              {side}
            </button>
          ))}
        </div>
      </div>

      {player.agent && (
        <div className={styles.agentSection}>
          {agentForSide ? (
            <div className={styles.agentCard}>
              <div className={styles.agentImage}>
                <AgentImage defIndex={agentForSide.def_index} name={agentForSide.item_name} />
              </div>
              <div className={styles.agentName}>{agentForSide.item_name}</div>
              {agentForSide.skin_name && (
                <div className={styles.agentType}>{agentForSide.skin_name}</div>
              )}
            </div>
          ) : (
            <div className={styles.noData}>No {activeSide} agent equipped</div>
          )}
        </div>
      )}

      <div className={styles.skinsGrid}>
        {visibleSkins.length > 0 ? (
          visibleSkins.map((skin, i) => {
            const tierColor = WEAR_COLOR[skin.wear_tier] || 'var(--muted)'
            return (
              <div key={i} className={styles.skinCard}>
                <div className={styles.skinImage}>
                  <SkinImage skin={skin} />
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
                {skin.side === 'both' && (
                  <div className={styles.bothBadge}>both sides</div>
                )}
              </div>
            )
          })
        ) : (
          <div className={styles.noData}>No {activeSide} skins equipped</div>
        )}
      </div>
    </div>
  )
}

export function LoadoutPanel({ demoId }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['demo-loadout', demoId],
    queryFn:  () => demosApi.getLoadout(demoId),
    enabled:  !!demoId,
  })

  if (isLoading) return <div className={styles.loading}>Loading loadout data…</div>
  if (error)     return <div className={styles.error}>Error loading loadout: {error.message}</div>
  if (!data)     return <div className={styles.error}>No loadout data available</div>

  const players = data.players || []

  return (
    <div className={styles.content}>
      {players.length > 0 ? (
        players.map((player, i) => (
          <PlayerCard key={player.steamid || player.name || i} player={player} />
        ))
      ) : (
        <div className={styles.noPlayers}>No player data available</div>
      )}
    </div>
  )
}

export default function Loadout() {
  const { demoId } = useParams()

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
      <LoadoutPanel demoId={demoId} />
    </div>
  )
}
