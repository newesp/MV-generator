import { useState, useEffect, useCallback, useRef } from 'react'
import { addRange, formatSeconds, rangePercentStyle } from './lipsyncRanges.js'
import {
  createIdlePreviewState,
  createPreviewErrorState,
  createProcessingPreviewState,
  createReadyPreviewState,
} from './sourcePreview.js'
import './index.css'

const API_BASE = 'http://localhost:8000'

function App() {
  const [mode, setMode] = useState('image_mv')
  const [audioFile, setAudioFile] = useState(null)
  const [images, setImages] = useState([])
  const [status, setStatus] = useState({ status: 'idle', message: '' })
  const [videoUrl, setVideoUrl] = useState(null)

  const [sourcePreview, setSourcePreview] = useState(createIdlePreviewState())
  const [rangeDraft, setRangeDraft] = useState({ start: 6, end: 13 })
  const [ranges, setRanges] = useState([])
  const [rangeError, setRangeError] = useState('')
  const [lipsyncJob, setLipsyncJob] = useState(null)
  const [lipsyncBusy, setLipsyncBusy] = useState(false)
  const [lipsyncVideoUrl, setLipsyncVideoUrl] = useState(null)
  const previewUrlRef = useRef('')
  const previewRequestRef = useRef(0)
  const lipsyncPollRef = useRef(null)

  const mvFile = sourcePreview.file
  const duration = sourcePreview.duration

  const handleAudioChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setAudioFile(e.target.files[0])
    }
  }

  const handleImagesChange = async (e) => {
    if (e.target.files) {
      const files = Array.from(e.target.files)
      setImages(files)
      for (const file of files) {
        const formData = new FormData()
        formData.append('file', file)
        try {
          await fetch(`${API_BASE}/upload/image`, {
            method: 'POST',
            body: formData,
          })
        } catch (err) {
          console.error('Failed to upload image', err)
        }
      }
    }
  }

  const handleGenerate = async () => {
    if (!audioFile) {
      alert('Please select an audio file.')
      return
    }

    const formData = new FormData()
    formData.append('file', audioFile)

    try {
      const res = await fetch(`${API_BASE}/generate`, {
        method: 'POST',
        body: formData,
      })
      if (res.ok) {
        checkStatus()
      } else {
        const data = await res.json()
        alert(data.message)
      }
    } catch (err) {
      console.error(err)
      alert('Failed to connect to backend.')
    }
  }

  const checkStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/status`)
      const data = await res.json()
      setStatus(data)

      if (data.status === 'running') {
        setTimeout(checkStatus, 2000)
      } else if (data.status === 'completed') {
        setVideoUrl(`${API_BASE}/download`)
      }
    } catch (err) {
      console.error(err)
    }
  }, [])

  useEffect(() => {
    checkStatus()
  }, [checkStatus])

  useEffect(() => {
    return () => {
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current)
      }
      if (lipsyncPollRef.current) {
        clearTimeout(lipsyncPollRef.current)
      }
    }
  }, [])

  const handleMvChange = (e) => {
    const file = e.target.files?.[0]
    previewRequestRef.current += 1
    const requestId = previewRequestRef.current
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current)
      previewUrlRef.current = ''
    }
    setRanges([])
    setRangeError('')
    setLipsyncJob(null)
    setLipsyncVideoUrl(null)

    if (!file) {
      setSourcePreview(createIdlePreviewState())
      return
    }

    setSourcePreview(createProcessingPreviewState(file))
    const previewUrl = URL.createObjectURL(file)
    const probe = document.createElement('video')
    probe.preload = 'metadata'
    probe.src = previewUrl

    probe.onloadedmetadata = () => {
      if (requestId !== previewRequestRef.current) {
        URL.revokeObjectURL(previewUrl)
        return
      }
      const nextDuration = probe.duration || 0
      previewUrlRef.current = previewUrl
      setSourcePreview(createReadyPreviewState(file, previewUrl, nextDuration))
      setRangeDraft((current) => ({
        start: Math.min(Number(current.start) || 0, Math.max(0, nextDuration - 1)),
        end: Math.min(Number(current.end) || nextDuration, nextDuration),
      }))
    }

    probe.onerror = () => {
      if (requestId !== previewRequestRef.current) {
        URL.revokeObjectURL(previewUrl)
        return
      }
      URL.revokeObjectURL(previewUrl)
      setSourcePreview(createPreviewErrorState(file, 'Could not load video metadata.'))
    }
  }

  const handleAddRange = () => {
    try {
      const nextRanges = addRange(ranges, rangeDraft, duration)
      setRanges(nextRanges)
      setRangeError('')
    } catch (err) {
      setRangeError(err.message)
    }
  }

  const removeRange = (indexToRemove) => {
    setRanges(ranges.filter((_, index) => index !== indexToRemove))
  }

  const pollLipsyncJob = useCallback(async (jobId) => {
    try {
      const res = await fetch(`${API_BASE}/jobs/${jobId}`)
      const data = await res.json()
      setLipsyncJob(data)
      if (data.status === 'completed') {
        setLipsyncVideoUrl(`${API_BASE}/jobs/${data.job_id}/download/final?t=${Date.now()}`)
        setLipsyncBusy(false)
        return
      }
      if (data.status === 'failed') {
        setLipsyncBusy(false)
        return
      }
      if (data.status === 'waiting_manual') {
        setLipsyncBusy(false)
        return
      }
      if (data.status === 'running' || data.status === 'pending') {
        lipsyncPollRef.current = setTimeout(() => pollLipsyncJob(jobId), 3000)
      }
    } catch (err) {
      console.error(err)
      setLipsyncBusy(false)
    }
  }, [])

  const startAutomaticLipsyncJob = async () => {
    if (!mvFile) {
      alert('Please select an MV file.')
      return
    }
    if (ranges.length === 0) {
      setRangeError('Add at least one lip-sync range.')
      return
    }

    setLipsyncBusy(true)
    setLipsyncVideoUrl(null)
    const formData = new FormData()
    formData.append('file', mvFile)
    formData.append('ranges', JSON.stringify(ranges))

    try {
      const res = await fetch(`${API_BASE}/lipsync-existing-mv`, {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      setLipsyncJob(data)
      if (!res.ok) {
        alert(data.message || 'Failed to prepare lip-sync job.')
        setLipsyncBusy(false)
      } else if (data.job_id) {
        pollLipsyncJob(data.job_id)
      }
    } catch (err) {
      console.error(err)
      alert('Failed to connect to backend.')
      setLipsyncBusy(false)
    }
  }

  const uploadProcessedSegment = async (segmentIndex, file) => {
    if (!lipsyncJob || !file) {
      return
    }
    setLipsyncBusy(true)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await fetch(`${API_BASE}/jobs/${lipsyncJob.job_id}/processed-segments/${segmentIndex}`, {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      setLipsyncJob(data)
      if (!res.ok) {
        alert(data.message || 'Failed to upload processed segment.')
      }
    } catch (err) {
      console.error(err)
      alert('Failed to connect to backend.')
    } finally {
      setLipsyncBusy(false)
    }
  }

  const resumeStitch = async () => {
    if (!lipsyncJob) {
      return
    }
    setLipsyncBusy(true)
    try {
      const res = await fetch(`${API_BASE}/jobs/${lipsyncJob.job_id}/resume-stitch`, {
        method: 'POST',
      })
      const data = await res.json()
      setLipsyncJob(data)
      if (res.ok && data.status === 'completed') {
        setLipsyncVideoUrl(`${API_BASE}/jobs/${data.job_id}/download/final?t=${Date.now()}`)
      } else if (!res.ok) {
        alert(data.message || 'Failed to resume stitching.')
      }
    } catch (err) {
      console.error(err)
      alert('Failed to connect to backend.')
    } finally {
      setLipsyncBusy(false)
    }
  }

  const processedSegments = lipsyncJob?.artifacts?.processed_segments || {}
  const allProcessedUploaded = lipsyncJob?.ranges?.length > 0
    && lipsyncJob.ranges.every((_, index) => processedSegments[String(index + 1)])

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>AI MV Generator</h1>
          <p>Generate a new MV or replace selected lip-sync ranges in an existing one.</p>
        </div>
        <div className="mode-switch" role="tablist" aria-label="Workflow mode">
          <button
            className={mode === 'image_mv' ? 'active' : ''}
            onClick={() => setMode('image_mv')}
            type="button"
          >
            Image MV
          </button>
          <button
            className={mode === 'lipsync_existing_mv' ? 'active' : ''}
            onClick={() => setMode('lipsync_existing_mv')}
            type="button"
          >
            Lip-sync Existing MV
          </button>
        </div>
      </header>

      <main>
        {mode === 'image_mv' ? (
          <ImageMvWorkflow
            audioFile={audioFile}
            images={images}
            status={status}
            videoUrl={videoUrl}
            onAudioChange={handleAudioChange}
            onImagesChange={handleImagesChange}
            onGenerate={handleGenerate}
          />
        ) : (
          <LipsyncExistingWorkflow
            sourcePreview={sourcePreview}
            duration={duration}
            rangeDraft={rangeDraft}
            ranges={ranges}
            rangeError={rangeError}
            lipsyncJob={lipsyncJob}
            lipsyncBusy={lipsyncBusy}
            lipsyncVideoUrl={lipsyncVideoUrl}
            allProcessedUploaded={allProcessedUploaded}
            onMvChange={handleMvChange}
            onRangeDraftChange={setRangeDraft}
            onAddRange={handleAddRange}
            onRemoveRange={removeRange}
            onPrepare={startAutomaticLipsyncJob}
            onUploadProcessed={uploadProcessedSegment}
            onResumeStitch={resumeStitch}
          />
        )}
      </main>
    </div>
  )
}

function ImageMvWorkflow({
  audioFile,
  images,
  status,
  videoUrl,
  onAudioChange,
  onImagesChange,
  onGenerate,
}) {
  return (
    <>
      <section className="workflow-grid">
        <div className="panel">
          <h2>Audio</h2>
          <input type="file" accept="audio/mp3,audio/wav" onChange={onAudioChange} />
          {audioFile && <p className="file-name">{audioFile.name}</p>}
        </div>

        <div className="panel">
          <h2>Images</h2>
          <input type="file" accept="image/png, image/jpeg" multiple onChange={onImagesChange} />
          <div className="badge-row">
            {images.map((img, idx) => (
              <span key={`${img.name}-${idx}`} className="badge">Image {idx + 1}</span>
            ))}
          </div>
        </div>
      </section>

      <section className="action-strip">
        <button
          className="btn-primary"
          onClick={onGenerate}
          disabled={status.status === 'running'}
          type="button"
        >
          {status.status === 'running' ? 'Generating...' : 'Generate MV'}
        </button>

        <StatusBox status={status.status} message={status.message} />
      </section>

      {videoUrl && (
        <ResultPreview title="Generated Music Video" videoUrl={videoUrl} downloadName="final_mv.mp4" />
      )}
    </>
  )
}

function LipsyncExistingWorkflow({
  sourcePreview,
  duration,
  rangeDraft,
  ranges,
  rangeError,
  lipsyncJob,
  lipsyncBusy,
  lipsyncVideoUrl,
  allProcessedUploaded,
  onMvChange,
  onRangeDraftChange,
  onAddRange,
  onRemoveRange,
  onPrepare,
  onUploadProcessed,
  onResumeStitch,
}) {
  return (
    <>
      <section className="workflow-grid lipsync-grid">
        <div className="panel">
          <h2>Source MV</h2>
          <input type="file" accept="video/mp4,video/quicktime" onChange={onMvChange} />
          {sourcePreview.file && <p className="file-name">{sourcePreview.file.name}</p>}
          {sourcePreview.status === 'processing' && (
            <div className="preview-processing" role="status" aria-live="polite">
              <span className="spinner" aria-hidden="true" />
              <span>Processing selected video...</span>
            </div>
          )}
          {sourcePreview.status === 'error' && (
            <p className="error-text">{sourcePreview.error}</p>
          )}
          {sourcePreview.status === 'ready' && (
            <video
              className="source-preview"
              src={sourcePreview.previewUrl}
              controls
            />
          )}
        </div>

        <div className="panel">
          <div className="panel-title-row">
            <h2>Ranges</h2>
            <span>{duration ? formatSeconds(duration) : 'No video loaded'}</span>
          </div>

          <Timeline duration={duration} ranges={ranges} />

          <div className="range-controls">
            <label>
              Start
              <input
                type="number"
                min="0"
                max={duration || undefined}
                step="0.1"
                value={rangeDraft.start}
                onChange={(event) => onRangeDraftChange({ ...rangeDraft, start: event.target.value })}
              />
            </label>
            <label>
              End
              <input
                type="number"
                min="0"
                max={duration || undefined}
                step="0.1"
                value={rangeDraft.end}
                onChange={(event) => onRangeDraftChange({ ...rangeDraft, end: event.target.value })}
              />
            </label>
            <button className="btn-secondary" type="button" onClick={onAddRange} disabled={!duration}>
              Add Range
            </button>
          </div>

          {rangeError && <p className="error-text">{rangeError}</p>}

          <div className="range-list">
            {ranges.map((range, index) => (
              <div className="range-item" key={`${range.start}-${range.end}`}>
                <span>Segment {index + 1}</span>
                <strong>{formatSeconds(range.start)} - {formatSeconds(range.end)}</strong>
                <button type="button" onClick={() => onRemoveRange(index)} aria-label={`Remove segment ${index + 1}`}>
                  Remove
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="action-strip">
        <button className="btn-primary" type="button" onClick={onPrepare} disabled={lipsyncBusy}>
          {lipsyncBusy ? 'Running...' : 'Generate Lip-sync MV'}
        </button>
        {lipsyncJob && <StatusBox status={lipsyncJob.status} message={lipsyncJob.message} />}
      </section>

      {lipsyncJob && (
        <section className="panel artifact-panel">
          <div className="panel-title-row">
            <h2>RunPod Job</h2>
            <span>{lipsyncJob.job_id}</span>
          </div>
          <ArtifactList artifacts={lipsyncJob.artifacts} />
          {lipsyncJob.status === 'waiting_manual' && (
            <>
              <div className="processed-grid">
                {lipsyncJob.ranges?.map((range, index) => {
                  const segmentIndex = index + 1
                  const uploaded = Boolean(lipsyncJob.artifacts?.processed_segments?.[String(segmentIndex)])
                  return (
                    <label className={uploaded ? 'processed-card uploaded' : 'processed-card'} key={segmentIndex}>
                      <span>Processed {segmentIndex}</span>
                      <strong>{formatSeconds(range.start)} - {formatSeconds(range.end)}</strong>
                      <input
                        type="file"
                        accept="video/mp4"
                        onChange={(event) => onUploadProcessed(segmentIndex, event.target.files?.[0])}
                      />
                    </label>
                  )
                })}
              </div>
              <button
                className="btn-primary"
                type="button"
                onClick={onResumeStitch}
                disabled={lipsyncBusy || !allProcessedUploaded}
              >
                Stitch Final MV
              </button>
            </>
          )}
        </section>
      )}

      {lipsyncVideoUrl && (
        <ResultPreview title="Lip-sync Existing MV Result" videoUrl={lipsyncVideoUrl} downloadName="lipsync_existing_mv.mp4" />
      )}
    </>
  )
}

function Timeline({ duration, ranges }) {
  return (
    <div className="timeline" aria-label="Lip-sync range timeline">
      <div className="timeline-track">
        {ranges.map((range) => (
          <span
            className="timeline-range"
            key={`${range.start}-${range.end}`}
            style={rangePercentStyle(range, duration)}
          />
        ))}
      </div>
      <div className="timeline-labels">
        <span>0.0s</span>
        <span>{duration ? formatSeconds(duration) : '0.0s'}</span>
      </div>
    </div>
  )
}

function ArtifactList({ artifacts = {} }) {
  const visibleArtifacts = [
    ['Bundle', artifacts.runpod_bundle],
    ['Source', artifacts.source],
    ['Segments', Array.isArray(artifacts.segments) ? artifacts.segments.join(' | ') : null],
    ['Audio', Array.isArray(artifacts.segment_audio) ? artifacts.segment_audio.join(' | ') : null],
    ['Final', artifacts.final],
  ].filter(([, value]) => value)

  return (
    <div className="artifact-list">
      {visibleArtifacts.map(([label, value]) => (
        <div className="artifact-row" key={label}>
          <span>{label}</span>
          <code>{value}</code>
        </div>
      ))}
    </div>
  )
}

function StatusBox({ status, message }) {
  return (
    <div className={`status-box ${status}`}>
      <p>{String(status || 'idle').toUpperCase()}</p>
      <p>{message || 'Ready'}</p>
    </div>
  )
}

function ResultPreview({ title, videoUrl, downloadName }) {
  return (
    <section className="result-section">
      <h2>{title}</h2>
      <video src={videoUrl} controls className="video-player" />
      <a href={videoUrl} download={downloadName} className="btn-secondary">Download Video</a>
    </section>
  )
}

export default App
