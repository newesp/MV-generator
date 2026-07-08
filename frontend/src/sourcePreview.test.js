import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  createProcessingPreviewState,
  createReadyPreviewState,
  createPreviewErrorState,
} from './sourcePreview.js'

test('createProcessingPreviewState stores the selected file without a preview url', () => {
  const file = { name: 'Gina-MV.mp4' }

  const state = createProcessingPreviewState(file)

  assert.equal(state.file, file)
  assert.equal(state.status, 'processing')
  assert.equal(state.previewUrl, '')
  assert.equal(state.duration, 0)
})

test('createReadyPreviewState exposes the stable preview url after metadata loads', () => {
  const file = { name: 'Gina-MV.mp4' }

  const state = createReadyPreviewState(file, 'blob:stable-url', 28.672)

  assert.equal(state.file, file)
  assert.equal(state.status, 'ready')
  assert.equal(state.previewUrl, 'blob:stable-url')
  assert.equal(state.duration, 28.672)
})

test('createPreviewErrorState keeps the selected file and error message', () => {
  const file = { name: 'broken.mp4' }

  const state = createPreviewErrorState(file, 'Could not load video metadata.')

  assert.equal(state.file, file)
  assert.equal(state.status, 'error')
  assert.equal(state.error, 'Could not load video metadata.')
})
