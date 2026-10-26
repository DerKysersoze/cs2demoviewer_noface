import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import MicroLabel from '../../components/ui/MicroLabel'
import LinkButton from '../../components/ui/LinkButton'
import MapReplayStage from '../../components/MapReplayStage'
import { floorForZ } from '../../components/mapFloors'
import { PLAYER_COLORS } from '../../components/playerColors'
import { ticksApi } from '../../api/ticks'
import styles from './Results.module.css'

const NO_HIDDEN = new Set()

/**
 * RoundMap — "this round on the 2D map" companion (option C, always on).
 *
 * Never collapses: the head carries the round label, floor badge and the
 * per-floor player distribution for the whole round, plus the "Open
 * fullscreen map" CTA (this round on the dedicated full-page 2D replay).
 * The body mounts the shared MapReplayStage (floor tabs, play/pause,
 * scrubber with kill + bomb markers) wide — it fills the companion column,
 * so the map is the main content of the Rounds tab while the kill feed
 * reads as a compact rail beside it.
 *
 * Both queries use the same keys as the 2D Map page
 * (['ticks', demoId, round] / ['map_info', map]), so the React Query cache
 * is shared — opening the map page warms this and vice versa.
 */
export default function RoundMap({ demoId, mapName, roundNum, kills = [], scoreboard = [] }) {
  const { data: tickData } = useQuery({
    queryKey: ['ticks', demoId, roundNum],
    queryFn:  () => ticksApi.getRound(demoId, roundNum),
    enabled:  !!demoId && !!roundNum,
    retry:    false,
  })

  const { data: mapInfo } = useQuery({
    queryKey: ['map_info', mapName],
    queryFn:  () => ticksApi.getMapInfo(mapName),
    enabled:  !!mapName,
    retry:    false,
  })
  const floors = useMemo(() => mapInfo?.floors || [], [mapInfo])

  const playerColorMap = useMemo(() => {
    const m = {}
    ;(scoreboard || []).forEach((p, i) => {
      m[p.name] = PLAYER_COLORS[i % PLAYER_COLORS.length]
    })
    return m
  }, [scoreboard])

  // Players who were on each floor at any point during the round
  // (frame 0 is spawn — everyone on the main floor, which would mislead)
  const floorSummary = useMemo(() => {
    if (floors.length < 2 || !tickData?.frames?.length) return null
    const per = {}
    for (const f of floors) per[f.name] = new Set()
    for (const fr of tickData.frames) {
      for (const pl of fr.p) {
        const fn = floorForZ(pl.z, floors, 'default')
        if (per[fn]) per[fn].add(pl.n)
      }
    }
    return floors.map(f => `${per[f.name].size} on ${f.label}`).join(' · ')
  }, [floors, tickData])

  return (
    <div className={styles.companion}>
      <div className={styles.companionHead}>
        <MicroLabel className={styles.metaLine}>
          ROUND {roundNum} · 2D MAP
        </MicroLabel>
        {floors.length > 1 && (
          <span className={styles.badgeGhost}>{floors.length} FLOORS</span>
        )}
        {floorSummary && (
          <span className={styles.companionSub}>{floorSummary}</span>
        )}
        <LinkButton
          to={`/map/${demoId}?round=${roundNum}`}
          className={styles.companionFull}
        >
          Open fullscreen map
        </LinkButton>
      </div>
      <div className={styles.companionBody}>
        <MapReplayStage
          tickData={tickData}
          mapName={mapName}
          kills={kills}
          roundNum={roundNum}
          hasTicks
          playerColorMap={playerColorMap}
          hiddenPlayers={NO_HIDDEN}
          variant="panel"
          wide
        />
      </div>
    </div>
  )
}
