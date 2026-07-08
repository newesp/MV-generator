import assert from 'node:assert/strict'
import { test } from 'node:test'
import { addRange, formatSeconds, rangePercentStyle } from './lipsyncRanges.js'

test('addRange appends and sorts non-overlapping ranges', () => {
  const ranges = addRange([{ start: 16, end: 23 }], { start: 6, end: 13 }, 28.672)

  assert.deepEqual(ranges, [
    { start: 6, end: 13 },
    { start: 16, end: 23 },
  ])
})

test('addRange rejects overlapping ranges', () => {
  assert.throws(
    () => addRange([{ start: 6, end: 13 }], { start: 12.9, end: 23 }, 28.672),
    /overlaps/,
  )
})

test('addRange rejects ranges outside known duration', () => {
  assert.throws(() => addRange([], { start: 6, end: 30 }, 28.672), /duration/)
})

test('rangePercentStyle maps a range to timeline percentages', () => {
  assert.deepEqual(rangePercentStyle({ start: 6, end: 13 }, 28), {
    left: '21.43%',
    width: '25%',
  })
})

test('formatSeconds keeps compact decimal labels', () => {
  assert.equal(formatSeconds(6), '6.0s')
  assert.equal(formatSeconds(6.25), '6.3s')
})
