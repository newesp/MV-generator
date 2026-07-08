export function createProcessingPreviewState(file) {
  return {
    file,
    status: 'processing',
    previewUrl: '',
    duration: 0,
    error: '',
  }
}

export function createReadyPreviewState(file, previewUrl, duration) {
  return {
    file,
    status: 'ready',
    previewUrl,
    duration,
    error: '',
  }
}

export function createPreviewErrorState(file, error) {
  return {
    file,
    status: 'error',
    previewUrl: '',
    duration: 0,
    error,
  }
}

export function createIdlePreviewState() {
  return {
    file: null,
    status: 'idle',
    previewUrl: '',
    duration: 0,
    error: '',
  }
}
