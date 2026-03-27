import { useQuery } from '@tanstack/react-query'
import { adminApi } from '../../api/admin'
import styles from './Admin.module.css'

const QUICK_QUERIES = [
  {
    group: 'Database',
    items: [
      { label: 'List demos',    sql: 'SELECT id, filename, map, uploaded_at FROM demos ORDER BY uploaded_at DESC;' },
      { label: 'Count demos',   sql: 'SELECT COUNT(*) AS total_demos FROM demos;' },
      { label: 'Demos by map',  sql: 'SELECT map, COUNT(*) AS count\nFROM demos GROUP BY map ORDER BY count DESC;' },
      { label: 'List tables',   sql: "SELECT name FROM sqlite_master WHERE type='table';" },
      { label: 'Integrity check', sql: 'PRAGMA integrity_check;' },
      { label: 'VACUUM',        sql: 'VACUUM;' },
    ],
  },
  {
    group: 'Kills & Rounds',
    items: [
      { label: 'Top fraggers (all demos)', sql: 'SELECT attacker, COUNT(*) AS kills\nFROM demo_kills\nGROUP BY attacker\nORDER BY kills DESC\nLIMIT 20;' },
      { label: 'Kills by weapon',          sql: 'SELECT weapon, COUNT(*) AS kills,\n  SUM(headshot) AS headshots\nFROM demo_kills\nGROUP BY weapon\nORDER BY kills DESC;' },
      { label: 'Kill count per demo',      sql: 'SELECT demo_id, COUNT(*) AS kills\nFROM demo_kills\nGROUP BY demo_id\nORDER BY kills DESC;' },
      { label: 'Rounds won by side',       sql: 'SELECT winner_side, COUNT(*) AS rounds\nFROM demo_rounds\nGROUP BY winner_side;' },
      { label: 'Round end reasons',        sql: 'SELECT reason, COUNT(*) AS count\nFROM demo_rounds\nGROUP BY reason\nORDER BY count DESC;' },
    ],
  },
  {
    group: 'Aim & Performance',
    items: [
      { label: 'Avg accuracy per player', sql: 'SELECT player_name, AVG(accuracy) AS avg_acc,\n  AVG(hs_hit_pct) AS avg_hs_pct,\n  AVG(kast) AS avg_kast\nFROM demo_aim\nGROUP BY player_name\nORDER BY avg_acc DESC\nLIMIT 20;' },
      { label: 'Hitgroup breakdown',      sql: 'SELECT player_name, hit_group,\n  SUM(hits) AS total_hits,\n  SUM(dmg) AS total_dmg\nFROM demo_aim_hitgroups\nGROUP BY player_name, hit_group\nORDER BY player_name, total_hits DESC;' },
      { label: 'Top weapon stats',        sql: 'SELECT player_name, weapon,\n  SUM(kills) AS kills,\n  SUM(hits) AS hits,\n  SUM(dmg) AS dmg\nFROM demo_aim_weapons\nGROUP BY player_name, weapon\nORDER BY kills DESC\nLIMIT 30;' },
    ],
  },
  {
    group: 'Cosmetics',
    items: [
      { label: 'Most common skins', sql: 'SELECT item_name, skin_name, COUNT(*) AS seen\nFROM demo_cosmetics\nWHERE is_agent = 0\nGROUP BY item_name, skin_name\nORDER BY seen DESC\nLIMIT 30;' },
      { label: 'StatTrak items',    sql: 'SELECT player_name, item_name, skin_name, wear_tier, stattrak\nFROM demo_cosmetics\nWHERE stattrak IS NOT NULL\nORDER BY stattrak DESC\nLIMIT 30;' },
      { label: 'Agents worn',       sql: 'SELECT player_name, item_name, side\nFROM demo_cosmetics\nWHERE is_agent = 1\nORDER BY player_name;' },
    ],
  },
]

export default function SchemaPanel({ onSelectQuery }) {
  const { data: schema, isLoading, isError } = useQuery({
    queryKey: ['admin-schema'],
    queryFn:  adminApi.schema,
  })

  return (
    <aside className={styles.schemaPanel}>
      <h3 className={styles.panelHeading}>Schema</h3>

      {isLoading && <span className={styles.dim}>Loading…</span>}
      {isError   && <span className={styles.errText}>Failed to load schema.</span>}

      {schema && Object.entries(schema).map(([tbl, cols]) => (
        <div key={tbl} className={styles.schemaTable}>
          <div
            className={styles.schemaTableName}
            onClick={() => onSelectQuery(`SELECT * FROM ${tbl} LIMIT 100;`)}
          >
            ▶ {tbl}
          </div>
          {cols.map(col => (
            <div key={col.name} className={styles.schemaCol}>
              <span className={styles.colName}>{col.name}</span>
              <span className={styles.colType}>{col.type || 'ANY'}</span>
              {col.pk ? <span className={styles.colPk}>PK</span> : null}
            </div>
          ))}
        </div>
      ))}

      <div className={styles.quickPanel}>
        {QUICK_QUERIES.map(section => (
          <div key={section.group}>
            <h3 className={styles.panelHeading} style={{ marginTop: 18 }}>{section.group}</h3>
            {section.items.map(item => (
              <button
                key={item.label}
                className={styles.quickBtn}
                onClick={() => onSelectQuery(item.sql)}
              >
                {item.label}
              </button>
            ))}
          </div>
        ))}
      </div>
    </aside>
  )
}
