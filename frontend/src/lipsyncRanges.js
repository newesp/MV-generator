export function addRange(existingRanges, nextRange, duration) {
  const normalized = normalizeRange(nextRange, duration)
  const ranges = [...existingRanges, normalized].sort((a, b) => a.start - b.start)
  for (let index = 1; index < ranges.length; index += 1) {
    if (ranges[index].start < ranges[index - 1].end) {
      throw new Error('Range overlaps an existing segment.')
    }
  }
  return ranges
}

export function normalizeRange(range, duration) {
  const start = Number(range.start)
  const end = Number(range.end)
  if (!Number.isFinite(start) || !Number.isFinite(end)) {
    throw new Error('Start and end must be numbers.')
  }
  if (start < 0) {
    throw new Error('Start must be 0 or greater.')
  }
  if (end <= start) {
    throw new Error('End must be greater than start.')
  }
  if (duration > 0 && end > duration) {
    throw new Error('Range cannot exceed the video duration.')
  }
  return { start: roundSeconds(start), end: roundSeconds(end) }
}

export function formatSeconds(value) {
  return `${Number(value || 0).toFixed(1)}s`
}

export function rangePercentStyle(range, duration) {
  if (!duration) {
    return { left: '0%', width: '0%' }
  }
  const left = roundPercent((range.start / duration) * 100)
  const width = roundPercent(((range.end - range.start) / duration) * 100)
  return { left: `${left}%`, width: `${width}%` }
}

function roundSeconds(value) {
  return Math.round(value * 1000) / 1000
}

function roundPercent(value) {
  return Math.round(value * 100) / 100
}
