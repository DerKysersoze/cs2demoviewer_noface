import { useRef, useState } from 'react'
import styles from './Upload.module.css'

/**
 * Slim upload strip (front page, mockup option A). Click anywhere (or the
 * Choose files button) to pick, or drop .dem files on it.
 */
export default function DropZone({ onFiles }) {
  const [dragOver, setDragOver] = useState(false)
  const inputRef  = useRef(null)

  function pickFiles(files) {
    const dems = [...files].filter(f => f.name.toLowerCase().endsWith('.dem'))
    if (dems.length) onFiles(dems, null)
    else             onFiles([], 'Only .dem files are supported.')
  }

  function onDrop(e) {
    e.preventDefault()
    setDragOver(false)
    pickFiles(e.dataTransfer.files)
  }

  function openPicker() {
    inputRef.current?.click()
  }

  function onInputChange() {
    pickFiles(inputRef.current.files)
    inputRef.current.value = ''
  }

  function onZoneClick(e) {
    if (e.target.closest('button')) return
    openPicker()
  }

  return (
    <div
      className={[styles.dropStrip, dragOver ? styles.dragOver : ''].join(' ')}
      onDragOver={e => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
      onClick={onZoneClick}
    >
      <span className={styles.dsIcon} aria-hidden="true">⬆</span>
      <div className={styles.dsText}>
        <strong>Drop .dem files here</strong>
        <span>· single file opens results instantly · multiple are queued</span>
      </div>
      <button
        type="button"
        className="btn btn-primary"
        onClick={e => { e.stopPropagation(); openPicker() }}
      >
        Choose files
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".dem"
        multiple
        style={{ display: 'none' }}
        onChange={onInputChange}
      />
    </div>
  )
}
