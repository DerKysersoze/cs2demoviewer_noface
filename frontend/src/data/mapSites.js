// Static bomb-site table for official CS2 maps (game data, not demo data).
// Used by the help panel on the dedicated map page.  Unknown maps → null
// (the panel simply omits the "Bomb sites" line instead of guessing).
export const MAP_BOMB_SITES = {
  de_ancient:   ['A', 'B'],
  de_anubis:    ['A', 'B'],
  de_ascent:    ['A', 'B'],
  de_basalt:    ['A', 'B'],
  de_dust2:     ['A', 'B'],
  de_inferno:   ['A', 'B'],
  de_italy:     ['A', 'B'],
  de_mirage:    ['A', 'B'],
  de_nuke:      ['A', 'B'],
  de_overpass:  ['A', 'B'],
  de_retake:    ['A', 'B'],
  de_seaweed:   ['A', 'B'],
  de_shortdust: ['A', 'B'],
  de_train:     ['A'],
  de_vertigo:   ['A'],
  de_moscow:    ['A'],
  de_piranesi:  ['A'],
}

export function bombSitesFor(mapName) {
  if (!mapName) return null
  return MAP_BOMB_SITES[mapName.toLowerCase()] || null
}
