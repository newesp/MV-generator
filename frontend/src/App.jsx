import { useState, useEffect, useCallback } from 'react'
import './index.css'

function App() {
  const [audioFile, setAudioFile] = useState(null)
  const [images, setImages] = useState([])
  const [status, setStatus] = useState({ status: 'idle', message: '' })
  const [videoUrl, setVideoUrl] = useState(null)

  const handleAudioChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setAudioFile(e.target.files[0])
    }
  }

  const handleImagesChange = async (e) => {
    if (e.target.files) {
      const files = Array.from(e.target.files)
      setImages(files)
      // Upload images immediately to inputs dir
      for (const file of files) {
        const formData = new FormData()
        formData.append('file', file)
        try {
          await fetch('http://localhost:8000/upload/image', {
            method: 'POST',
            body: formData,
          })
        } catch (err) {
          console.error("Failed to upload image", err)
        }
      }
    }
  }

  const handleGenerate = async () => {
    if (!audioFile) {
      alert("Please select an audio file!")
      return
    }

    const formData = new FormData()
    formData.append('file', audioFile)

    try {
      const res = await fetch('http://localhost:8000/generate', {
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
      alert("Failed to connect to backend.")
    }
  }

  const checkStatus = useCallback(async () => {
    try {
      const res = await fetch('http://localhost:8000/status')
      const data = await res.json()
      setStatus(data)
      
      if (data.status === 'running') {
        setTimeout(checkStatus, 2000)
      } else if (data.status === 'completed') {
        setVideoUrl('http://localhost:8000/download')
      }
    } catch (err) {
      console.error(err)
    }
  }, [])

  useEffect(() => {
    checkStatus()
  }, [checkStatus])

  return (
    <div className="container">
      <header>
        <h1>AI MV Generator</h1>
        <p>Sync your images and audio into a music video automatically.</p>
      </header>

      <main>
        <section className="upload-section">
          <div className="card">
            <h2>1. Upload Audio</h2>
            <input type="file" accept="audio/mp3,audio/wav" onChange={handleAudioChange} />
            {audioFile && <p className="file-name">Selected: {audioFile.name}</p>}
          </div>

          <div className="card">
            <h2>2. Upload Images</h2>
            <p className="hint">Upload multiple images. They will be cycled if not enough for all beats.</p>
            <input type="file" accept="image/png, image/jpeg" multiple onChange={handleImagesChange} />
            <div className="image-preview-container">
              {images.map((img, idx) => (
                <span key={idx} className="badge">Image {idx+1}</span>
              ))}
            </div>
          </div>
        </section>

        <section className="action-section">
          <button 
            className="btn-primary"
            onClick={handleGenerate}
            disabled={status.status === 'running'}
          >
            {status.status === 'running' ? 'Generating...' : 'Generate MV'}
          </button>
          
          <div className={`status-box ${status.status}`}>
            <p>Status: {status.status.toUpperCase()}</p>
            <p>{status.message}</p>
          </div>
        </section>

        {videoUrl && (
          <section className="result-section">
            <h2>Generated Music Video</h2>
            <video src={videoUrl} controls autoPlay className="video-player" />
            <br />
            <a href={videoUrl} download="final_mv.mp4" className="btn-secondary">Download Video</a>
          </section>
        )}
      </main>
    </div>
  )
}

export default App
