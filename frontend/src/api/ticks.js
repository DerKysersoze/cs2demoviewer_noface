export const ticksApi = {
  getRound: (demoId, round) =>
    fetch(`/api/ticks/${demoId}/${round}`).then(res => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return res.json()
    }),

  getMapInfo: (mapName) =>
    fetch(`/api/map_info/${mapName}`).then(res => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return res.json()
    }),

  mapImageUrl: (mapName) => `/api/map_image/${mapName}`,
}
