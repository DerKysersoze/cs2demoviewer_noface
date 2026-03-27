const WEAPON_META = {
  ak47:                 { cat: 'rifle',   abbr: 'AK-47',  label: 'AK-47' },
  m4a1:                 { cat: 'rifle',   abbr: 'M4A4',   label: 'M4A4' },
  m4a1_silencer:        { cat: 'rifle',   abbr: 'M4A1-S', label: 'M4A1-S' },
  sg556:                { cat: 'rifle',   abbr: 'SG553',  label: 'SG 553' },
  aug:                  { cat: 'rifle',   abbr: 'AUG',    label: 'AUG' },
  galilar:              { cat: 'rifle',   abbr: 'GALIL',  label: 'Galil AR' },
  galil:                { cat: 'rifle',   abbr: 'GALIL',  label: 'Galil AR' },
  famas:                { cat: 'rifle',   abbr: 'FAMAS',  label: 'FAMAS' },
  awp:                  { cat: 'sniper',  abbr: 'AWP',    label: 'AWP' },
  ssg08:                { cat: 'sniper',  abbr: 'SSG08',  label: 'SSG 08' },
  g3sg1:                { cat: 'sniper',  abbr: 'G3SG1',  label: 'G3SG1' },
  scar20:               { cat: 'sniper',  abbr: 'SCAR20', label: 'SCAR-20' },
  deagle:               { cat: 'pistol',  abbr: 'DEAGLE', label: 'Desert Eagle' },
  glock:                { cat: 'pistol',  abbr: 'GLOCK',  label: 'Glock-18' },
  usp_silencer:         { cat: 'pistol',  abbr: 'USP-S',  label: 'USP-S' },
  hkp2000:              { cat: 'pistol',  abbr: 'P2000',  label: 'P2000' },
  p250:                 { cat: 'pistol',  abbr: 'P250',   label: 'P250' },
  tec9:                 { cat: 'pistol',  abbr: 'TEC-9',  label: 'Tec-9' },
  fiveseven:            { cat: 'pistol',  abbr: '57E',    label: 'Five-SeveN' },
  cz75a:                { cat: 'pistol',  abbr: 'CZ75',   label: 'CZ75-Auto' },
  revolver:             { cat: 'pistol',  abbr: 'R8',     label: 'R8 Revolver' },
  elite:                { cat: 'pistol',  abbr: 'ELITE',  label: 'Dual Berettas' },
  mp9:                  { cat: 'smg',     abbr: 'MP9',    label: 'MP9' },
  mp7:                  { cat: 'smg',     abbr: 'MP7',    label: 'MP7' },
  mp5sd:                { cat: 'smg',     abbr: 'MP5-SD', label: 'MP5-SD' },
  ump45:                { cat: 'smg',     abbr: 'UMP-45', label: 'UMP-45' },
  p90:                  { cat: 'smg',     abbr: 'P90',    label: 'P90' },
  bizon:                { cat: 'smg',     abbr: 'BIZON',  label: 'PP-Bizon' },
  mac10:                { cat: 'smg',     abbr: 'MAC-10', label: 'MAC-10' },
  nova:                 { cat: 'shotgun', abbr: 'NOVA',   label: 'Nova' },
  xm1014:               { cat: 'shotgun', abbr: 'XM1014', label: 'XM1014' },
  mag7:                 { cat: 'shotgun', abbr: 'MAG-7',  label: 'MAG-7' },
  sawedoff:             { cat: 'shotgun', abbr: 'SAWOFF', label: 'Sawed-Off' },
  m249:                 { cat: 'heavy',   abbr: 'M249',   label: 'M249' },
  negev:                { cat: 'heavy',   abbr: 'NEGEV',  label: 'Negev' },
  flashbang:            { cat: 'grenade', abbr: 'FLASH',  label: 'Flashbang' },
  smokegrenade:         { cat: 'grenade', abbr: 'SMOKE',  label: 'Smoke Grenade' },
  hegrenade:            { cat: 'grenade', abbr: 'HE',     label: 'HE Grenade' },
  molotov:              { cat: 'grenade', abbr: 'MOLOTV', label: 'Molotov' },
  incgrenade:           { cat: 'grenade', abbr: 'INC',    label: 'Incendiary' },
  decoy:                { cat: 'grenade', abbr: 'DECOY',  label: 'Decoy Grenade' },
  inferno:              { cat: 'grenade', abbr: 'FIRE',   label: 'Molotov Fire' },
  taser:                { cat: 'pistol',  abbr: 'ZEUS',   label: 'Zeus x27' },
  knife:                { cat: 'knife',   abbr: 'KNIFE',  label: 'Knife' },
  knife_t:              { cat: 'knife',   abbr: 'KNIFE',  label: 'Knife' },
  bayonet:              { cat: 'knife',   abbr: 'KNIFE',  label: 'Bayonet' },
  knife_survival_bowie: { cat: 'knife',   abbr: 'KNIFE',  label: 'Bowie Knife' },
  knife_tactical:       { cat: 'knife',   abbr: 'KNIFE',  label: 'Huntsman Knife' },
  knife_flip:           { cat: 'knife',   abbr: 'KNIFE',  label: 'Flip Knife' },
  knife_gut:            { cat: 'knife',   abbr: 'KNIFE',  label: 'Gut Knife' },
  knife_karambit:       { cat: 'knife',   abbr: 'KNIFE',  label: 'Karambit' },
  knife_m9_bayonet:     { cat: 'knife',   abbr: 'KNIFE',  label: 'M9 Bayonet' },
  knife_falchion:       { cat: 'knife',   abbr: 'KNIFE',  label: 'Falchion Knife' },
  knife_butterfly:      { cat: 'knife',   abbr: 'KNIFE',  label: 'Butterfly Knife' },
  knife_push:           { cat: 'knife',   abbr: 'KNIFE',  label: 'Shadow Daggers' },
  knife_cord:           { cat: 'knife',   abbr: 'KNIFE',  label: 'Paracord Knife' },
  knife_canis:          { cat: 'knife',   abbr: 'KNIFE',  label: 'Survival Knife' },
  knife_ursus:          { cat: 'knife',   abbr: 'KNIFE',  label: 'Ursus Knife' },
  knife_gypsy_jackknife:{ cat: 'knife',   abbr: 'KNIFE',  label: 'Navaja Knife' },
  knife_outdoor:        { cat: 'knife',   abbr: 'KNIFE',  label: 'Nomad Knife' },
  knife_stiletto:       { cat: 'knife',   abbr: 'KNIFE',  label: 'Stiletto Knife' },
  knife_widowmaker:     { cat: 'knife',   abbr: 'KNIFE',  label: 'Talon Knife' },
  knife_skeleton:       { cat: 'knife',   abbr: 'KNIFE',  label: 'Skeleton Knife' },
  knife_kukri:          { cat: 'knife',   abbr: 'KNIFE',  label: 'Kukri Knife' },
}

const CAT_COLOR = {
  rifle:   '#ff9f1c',
  sniper:  '#f87171',
  pistol:  '#38bdf8',
  smg:     '#6bcb77',
  shotgun: '#fbbf24',
  heavy:   '#c77dff',
  grenade: '#2ec4b6',
  knife:   '#94a3b8',
  unknown: '#6b7280',
}

export default function WeaponIcon({ weapon, catHint }) {
  const key  = (weapon || '').toLowerCase().replace(/^weapon_/, '')
  const meta = WEAPON_META[key]
  const cat  = meta ? meta.cat  : (catHint || 'unknown')
  const abbr = meta ? meta.abbr : (catHint === 'knife' ? 'KNIFE' : key.toUpperCase().slice(0, 6))
  const label= meta ? meta.label : weapon

  return (
    <span
      className="wpn-icon"
      style={{ background: CAT_COLOR[cat] || CAT_COLOR.unknown }}
      data-tip={`${label}\nCategory: ${cat}`}
    >
      {abbr}
    </span>
  )
}
