// Test runner: node --test tests/plyParser.test.mjs
// Verifies the PLY parser handles 4-component (RGBA) color properties correctly.
// Regression test for the bug where the 3D preview showed a black window
// after optimization completed because the parser only read 3 of the 4 color
// bytes per vertex, leaving a 1-byte-per-vertex offset drift that mis-aligned
// face indices.

import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const PLY_TYPE_SIZES = {
  float: 4, double: 8, uchar: 1, char: 1, ushort: 2, short: 2, int: 4, uint: 4,
}

function parsePLYHeader(buffer) {
  const decoder = new TextDecoder('ascii')
  const header = decoder.decode(new Uint8Array(buffer, 0, Math.min(buffer.byteLength, 4096)))
  const end = header.indexOf('end_header')
  if (end === -1) throw new Error('Invalid PLY: no end_header')
  const headerLines = header.substring(0, end).split('\n').filter(l => l.trim())

  let vertexCount = 0
  let faceCount = 0
  let vertexStride = 0
  let colorStride = 0
  let hasColors = false

  for (const line of headerLines) {
    const parts = line.trim().split(/\s+/)
    if (parts[0] === 'element') {
      if (parts[1] === 'vertex') vertexCount = parseInt(parts[2])
      if (parts[1] === 'face') faceCount = parseInt(parts[2])
    } else if (parts[0] === 'property') {
      const typeName = parts[1]
      const byteSize = PLY_TYPE_SIZES[typeName]
      if (byteSize === undefined) continue
      vertexStride += byteSize
      const name = parts[2].toLowerCase()
      if (name === 'red' || name === 'green' || name === 'blue' || name === 'r' || name === 'g' || name === 'b') {
        colorStride += byteSize
        hasColors = true
      }
    }
  }
  const headerLen = end + 'end_header'.length + 1
  return { headerLen, vertexCount, faceCount, vertexStride, colorStride, hasColors }
}

function parseColoredMesh(buffer) {
  const dv = new DataView(buffer)
  const { headerLen, vertexCount, faceCount, vertexStride, colorStride } = parsePLYHeader(buffer)
  if (vertexCount === 0 || faceCount === 0) {
    throw new Error('Empty PLY mesh')
  }

  let offset = headerLen
  const positions = new Float32Array(vertexCount * 3)
  const hasColors = colorStride > 0
  const colors = hasColors ? new Float32Array(vertexCount * 3) : null

  const positionBytes = 12
  const colorReadBytes = Math.min(colorStride, 3)
  const skipBytes = Math.max(0, vertexStride - positionBytes - colorReadBytes)

  for (let i = 0; i < vertexCount; i++) {
    positions[i * 3] = dv.getFloat32(offset, true); offset += 4
    positions[i * 3 + 1] = dv.getFloat32(offset, true); offset += 4
    positions[i * 3 + 2] = dv.getFloat32(offset, true); offset += 4
    if (hasColors && colors) {
      colors[i * 3] = dv.getUint8(offset) / 255; offset += 1
      colors[i * 3 + 1] = dv.getUint8(offset) / 255; offset += 1
      colors[i * 3 + 2] = dv.getUint8(offset) / 255; offset += 1
      offset += skipBytes
    }
  }

  const indices = new Uint32Array(faceCount * 3)
  for (let i = 0; i < faceCount; i++) {
    const count = dv.getUint8(offset); offset += 1
    if (count === 3) {
      indices[i * 3] = dv.getUint32(offset, true); offset += 4
      indices[i * 3 + 1] = dv.getUint32(offset, true); offset += 4
      indices[i * 3 + 2] = dv.getUint32(offset, true); offset += 4
    } else {
      offset += count * 4
    }
  }

  return { positions, colors, indices }
}

function buildTestPLY() {
  const vertexCount = 3
  const faceCount = 1

  const header = `ply
format binary_little_endian 1.0
element vertex ${vertexCount}
property float x
property float y
property float z
property uchar red
property uchar green
property uchar blue
property uchar alpha
element face ${faceCount}
property list uchar int vertex_indices
end_header
`

  const buffer = new ArrayBuffer(4096)
  const view = new Uint8Array(buffer)
  let offset = 0

  for (let i = 0; i < header.length; i++) {
    view[offset++] = header.charCodeAt(i)
  }

  view[offset++] = 0; view[offset++] = 0; view[offset++] = 0; view[offset++] = 0
  view[offset++] = 0; view[offset++] = 0; view[offset++] = 0; view[offset++] = 0
  view[offset++] = 0; view[offset++] = 0; view[offset++] = 0; view[offset++] = 0
  view[offset++] = 255; view[offset++] = 0; view[offset++] = 0; view[offset++] = 255

  view[offset++] = 0; view[offset++] = 0; view[offset++] = 0x80; view[offset++] = 0x3f
  view[offset++] = 0; view[offset++] = 0; view[offset++] = 0; view[offset++] = 0
  view[offset++] = 0; view[offset++] = 0; view[offset++] = 0; view[offset++] = 0
  view[offset++] = 0; view[offset++] = 255; view[offset++] = 0; view[offset++] = 255

  view[offset++] = 0; view[offset++] = 0; view[offset++] = 0; view[offset++] = 0
  view[offset++] = 0; view[offset++] = 0; view[offset++] = 0x80; view[offset++] = 0x3f
  view[offset++] = 0; view[offset++] = 0; view[offset++] = 0; view[offset++] = 0
  view[offset++] = 0; view[offset++] = 0; view[offset++] = 255; view[offset++] = 255

  view[offset++] = 3
  view[offset++] = 0; view[offset++] = 0; view[offset++] = 0; view[offset++] = 0
  view[offset++] = 1; view[offset++] = 0; view[offset++] = 0; view[offset++] = 0
  view[offset++] = 2; view[offset++] = 0; view[offset++] = 0; view[offset++] = 0

  return buffer.slice(0, offset)
}

test('parsePLYHeader handles 4-component colors (RGBA)', () => {
  const buffer = buildTestPLY()
  const header = parsePLYHeader(buffer)
  assert.equal(header.vertexCount, 3)
  assert.equal(header.faceCount, 1)
  assert.equal(header.vertexStride, 16)
  assert.equal(header.colorStride, 3)
  assert.equal(header.hasColors, true)
})

test('parseColoredMesh handles 4-component colors with alpha', () => {
  const buffer = buildTestPLY()
  const { positions, colors, indices } = parseColoredMesh(buffer)

  assert.equal(positions.length, 9)
  assert.equal(colors.length, 9)
  assert.equal(indices.length, 3)

  assert.equal(positions[0], 0)
  assert.equal(positions[1], 0)
  assert.equal(positions[2], 0)

  assert.ok(Math.abs(positions[3] - 1) < 0.001, 'positions[3] should be 1')
  assert.equal(positions[4], 0)
  assert.equal(positions[5], 0)

  assert.equal(positions[6], 0)
  assert.ok(Math.abs(positions[7] - 1) < 0.001, 'positions[7] should be 1')
  assert.equal(positions[8], 0)

  assert.ok(Math.abs(colors[0] - 1) < 0.01, 'colors[0] should be 1.0')
  assert.equal(colors[1], 0)
  assert.equal(colors[2], 0)

  assert.equal(colors[3], 0)
  assert.ok(Math.abs(colors[4] - 1) < 0.01, 'colors[4] should be 1.0')
  assert.equal(colors[5], 0)

  assert.equal(colors[6], 0)
  assert.equal(colors[7], 0)
  assert.ok(Math.abs(colors[8] - 1) < 0.01, 'colors[8] should be 1.0')

  assert.equal(indices[0], 0)
  assert.equal(indices[1], 1)
  assert.equal(indices[2], 2)
})

test('parsePLYHeader handles 3-component colors (no alpha)', () => {
  const header = `ply
format binary_little_endian 1.0
element vertex 3
property float x
property float y
property float z
property uchar red
property uchar green
property uchar blue
element face 1
property list uchar int vertex_indices
end_header
`
  const buffer = new ArrayBuffer(4096)
  const view = new Uint8Array(buffer)
  for (let i = 0; i < header.length; i++) view[i] = header.charCodeAt(i)

  const parsed = parsePLYHeader(buffer)
  assert.equal(parsed.vertexCount, 3)
  assert.equal(parsed.faceCount, 1)
  assert.equal(parsed.vertexStride, 15)
  assert.equal(parsed.colorStride, 3)
  assert.equal(parsed.hasColors, true)
})

test('parsePLYHeader handles no colors (position-only)', () => {
  const header = `ply
format binary_little_endian 1.0
element vertex 3
property float x
property float y
property float z
element face 1
property list uchar int vertex_indices
end_header
`
  const buffer = new ArrayBuffer(4096)
  const view = new Uint8Array(buffer)
  for (let i = 0; i < header.length; i++) view[i] = header.charCodeAt(i)

  const parsed = parsePLYHeader(buffer)
  assert.equal(parsed.vertexCount, 3)
  assert.equal(parsed.faceCount, 1)
  assert.equal(parsed.vertexStride, 12)
  assert.equal(parsed.colorStride, 0)
  assert.equal(parsed.hasColors, false)
})

test('real PLY file from optimization is parseable with correct stride', () => {
  const checkpointsDir = '/home/mei/Projects/AutoForge2/checkpoints'
  if (!fs.existsSync(checkpointsDir)) {
    return
  }

  const dirs = fs.readdirSync(checkpointsDir).filter(d => {
    try {
      const stat = fs.statSync(path.join(checkpointsDir, d))
      return stat.isDirectory()
    } catch {
      return false
    }
  })

  let foundValid = false
  for (const dir of dirs) {
    const plyPath = path.join(checkpointsDir, dir, 'final_model_colored.ply')
    if (!fs.existsSync(plyPath)) continue
    const stat = fs.statSync(plyPath)
    if (stat.size < 1024) continue

    const buffer = fs.readFileSync(plyPath)
    const ab = buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength)
    const parsed = parsePLYHeader(ab)

    assert.ok(parsed.vertexCount > 0, `vertexCount should be > 0, got ${parsed.vertexCount}`)
    assert.ok(parsed.faceCount > 0, `faceCount should be > 0, got ${parsed.faceCount}`)
    assert.ok(parsed.colorStride > 0, `colorStride should be > 0 (colors present)`)

    const skipBytes = Math.max(0, parsed.vertexStride - 12 - Math.min(parsed.colorStride, 3))
    assert.ok(skipBytes >= 0, `skipBytes should be >= 0, got ${skipBytes}`)
    foundValid = true
    break
  }

  if (!foundValid) {
    console.log('No checkpoints with PLY files found, skipping real PLY test')
  }
})