import styles from './Upload.module.css'

const ICON  = { queued: '⏳', uploading: '🔄', parsing: '⚙️', done: '✅', error: '❌' }
const STATE = { queued: '', uploading: styles.qiUploading, parsing: styles.qiUploading, done: styles.qiDone, error: styles.qiError }

export default function QueueView({ items, summary, onUploadMore }) {
  const processed = items.filter(it => it.state === 'done' || it.state === 'error').length

  return (
    <div className={styles.queueWrap}>
      <div className={styles.queueHeader}>
        <span>
          {summary
            ? 'Upload complete'
            : `${processed} / ${items.length} processed`}
        </span>
      </div>

      <div className={styles.queueList}>
        {items.map(item => (
          <div key={item.idx} className={[styles.qi, STATE[item.state]].join(' ')}>
            <span className={styles.qiIcon}>{ICON[item.state]}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className={styles.qiName} title={item.name}>{item.name}</div>
              {item.state === 'uploading' && (
                <div className={styles.qiProgress}>
                  <div
                    className={styles.qiProgressFill}
                    style={{ width: item.progress + '%', animation: item.progress > 0 ? 'none' : undefined }}
                  />
                </div>
              )}
            </div>
            <span className={styles.qiStatus}>
              {item.state === 'queued'    && 'Queued'}
              {item.state === 'uploading' && (item.progress > 0 ? `Uploading ${item.progress}%` : 'Uploading…')}
              {item.state === 'parsing'   && 'Parsing…'}
              {item.state === 'done'      && 'Done'}
              {item.state === 'error'     && (item.error || 'Error')}
            </span>
          </div>
        ))}
      </div>

      {summary && (
        <div className={styles.queueSummary}>
          <p>
            {summary.errors === 0
              ? `All ${summary.done} demo${summary.done !== 1 ? 's' : ''} uploaded successfully.`
              : `${summary.done} succeeded, ${summary.errors} failed.`}
          </p>
          <button className="btn btn-ghost" onClick={onUploadMore}>
            Upload More
          </button>
        </div>
      )}
    </div>
  )
}
