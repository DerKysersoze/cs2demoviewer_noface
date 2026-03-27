import { useRef, useState } from 'react'
import styles from './Upload.module.css'

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

  function onInputChange() {
    pickFiles(inputRef.current.files)
    inputRef.current.value = ''
  }

  function onZoneClick(e) {
    if (e.target.tagName === 'BUTTON') return
    inputRef.current.click()
  }

  return (
    <div
      className={[styles.dropZone, dragOver ? styles.dragOver : ''].join(' ')}
      onDragOver={e => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
      onClick={onZoneClick}
    >
      <div className={styles.dropIcon}>🎮</div>
      <strong>Drop .dem files here</strong>
      <p>Single file opens the viewer · Multiple files are queued and saved</p>
      <button className="btn btn-primary" style={{ marginTop: 20 }}>
        Choose Files
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
