import { useState } from 'react'

/**
 * Generic sortable table.
 *
 * Props:
 *   columns  — array of { key, label, className?, render?(value, row) => node }
 *   rows     — array of objects
 *   defaultSort — key to sort by initially
 *   defaultDir  — 1 (asc) or -1 (desc), default -1
 */
export default function SortableTable({ columns, rows, defaultSort, defaultDir = -1 }) {
  const [sortCol, setSortCol] = useState(defaultSort || columns[0]?.key)
  const [sortDir, setSortDir] = useState(defaultDir)

  function handleSort(key) {
    if (key === sortCol) {
      setSortDir(d => d * -1)
    } else {
      setSortCol(key)
      setSortDir(-1)
    }
  }

  const sorted = [...rows].sort((a, b) => {
    const av = a[sortCol] ?? -Infinity
    const bv = b[sortCol] ?? -Infinity
    if (typeof av === 'string') return sortDir * av.localeCompare(bv)
    return sortDir * (bv - av)
  })

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map(col => (
              <th
                key={col.key}
                className={[
                  'sortable',
                  col.className,
                  col.key === sortCol ? (sortDir === -1 ? 'sort-desc' : 'sort-asc') : '',
                ].filter(Boolean).join(' ')}
                onClick={() => handleSort(col.key)}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr key={row.id ?? i}>
              {columns.map(col => (
                <td key={col.key} className={col.className}>
                  {col.render ? col.render(row[col.key], row) : row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
