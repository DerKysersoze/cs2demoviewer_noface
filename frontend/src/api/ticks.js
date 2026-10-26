export const ticksApi = {
  getRound: (demoId, round) =>
    fetch(`/api/ticks/${demoId}/${round}`).then(res => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return res.json()
    }),

  getMapInfo: (mapName) =>
    fetch(`/api/map_info/${encodeURIComponent(mapName)}`).then(res => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return res.json()
    }),

  mapImageUrl: (mapName, floor) => {
    const base = `/api/map_image/${encodeURIComponent(mapName)}`
    return floor && floor !== 'default' ? `${base}/${encodeURIComponent(floor)}` : base
  },

  mapsReady: () =>
    fetch('/api/maps_ready').then(res => res.json()),

  downloadMaps: () =>
    fetch('/api/download_maps', { method: 'POST' }).then(res => res.json()),
}
