import zlib from 'zlib'

const CRC_TABLE: number[] = (() => {
  const table: number[] = []
  for (let n = 0; n < 256; n++) {
    let c = n
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    table[n] = c >>> 0
  }
  return table
})()

function crc32(buf: Buffer): number {
  let c = 0xffffffff
  for (const b of buf) c = CRC_TABLE[(c ^ b) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}

function chunk(type: string, payload: Buffer): Buffer {
  const len = Buffer.alloc(4)
  len.writeUInt32BE(payload.length)
  const typeBuf = Buffer.from(type)
  const crcBuf = Buffer.alloc(4)
  crcBuf.writeUInt32BE(crc32(Buffer.concat([typeBuf, payload])))
  return Buffer.concat([len, typeBuf, payload, crcBuf])
}

/** Build a valid (correct-CRC), decoder-strict-safe solid-color RGB PNG. */
export function makeSolidPng(width: number, height: number, rgb: [number, number, number]): Buffer {
  const stride = width * 3 + 1
  const scanlines = Buffer.alloc(stride * height)
  for (let y = 0; y < height; y++) {
    scanlines[y * stride] = 0
    for (let x = 0; x < width; x++) {
      const off = y * stride + 1 + x * 3
      scanlines[off] = rgb[0]
      scanlines[off + 1] = rgb[1]
      scanlines[off + 2] = rgb[2]
    }
  }
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(width, 0)
  ihdr.writeUInt32BE(height, 4)
  ihdr[8] = 8 // bit depth
  ihdr[9] = 2 // color type RGB
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', zlib.deflateSync(scanlines)),
    chunk('IEND', Buffer.alloc(0)),
  ])
}
