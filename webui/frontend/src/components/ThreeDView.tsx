import React, { useEffect, useState } from 'react'
import { Canvas, useThree } from '@react-three/fiber'
import { OrbitControls, Html } from '@react-three/drei'
import * as THREE from 'three'
import { cn } from '../lib/utils'
import { parseColoredMesh } from '../lib/plyParser'
import type { StackSegment } from '../lib/colorStack'

interface ThreeDViewProps {
  stlUrl?: string | null
  coloredPlyUrl?: string | null
  /** Rendered instead of a fetched mesh when there's no optimization result
   * yet — a simple stacked-slab preview of the color sliders' filament
   * stack, so the panel shows something meaningful before the first run. */
  stackSegments?: StackSegment[]
  className?: string
}

const ColorStackPreview: React.FC<{ segments: StackSegment[] }> = ({ segments }) => {
  if (segments.length === 0) return null
  const maxLayer = segments[segments.length - 1].layerIndex
  const footprint = 3
  const totalHeight = 3
  const bandHeight = totalHeight / maxLayer

  return (
    <group position={[0, -totalHeight / 2, 0]}>
      {segments.map((seg) => (
        <mesh key={seg.layerIndex} position={[0, (seg.layerIndex - 0.5) * bandHeight, 0]}>
          <boxGeometry args={[footprint, bandHeight * 1.02, footprint]} />
          <meshStandardMaterial color={seg.color} roughness={0.7} metalness={0.1} toneMapped={false} />
        </mesh>
      ))}
    </group>
  )
}

function centerAndScaleGeom(geom: THREE.BufferGeometry): THREE.BufferGeometry {
  geom.computeBoundingBox()
  const box = geom.boundingBox
  if (!box || !isFinite(box.max.x - box.min.x)) return geom
  const center = new THREE.Vector3()
  box.getCenter(center)
  geom.translate(-center.x, -center.y, -center.z)
  const size = new THREE.Vector3()
  box.getSize(size)
  const maxDim = Math.max(size.x, size.y, size.z, 0.001)
  const targetSize = 4
  const scale = targetSize / maxDim
  if (isFinite(scale) && scale > 0) {
    geom.scale(scale, scale, scale)
  }
  return geom
}

const ColoredMesh: React.FC<{ plyUrl: string }> = ({ plyUrl }) => {
  const [mesh, setMesh] = useState<{ geom: THREE.BufferGeometry; colors: boolean } | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    fetch(plyUrl)
      .then(r => r.arrayBuffer())
      .then(buffer => {
        if (cancelled) return

        const { positions, colors, indices } = parseColoredMesh(buffer)

        const vertexCount = positions.length / 3
        if (vertexCount === 0 || indices.length === 0) {
          throw new Error('Empty PLY mesh')
        }

        const geom = new THREE.BufferGeometry()
        geom.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
        geom.setIndex(new THREE.BufferAttribute(indices, 1))
        geom.computeVertexNormals()
        geom.computeBoundingBox()

        const centered = centerAndScaleGeom(geom)

        if (colors) {
          const colorAttr = new THREE.Float32BufferAttribute(colors, 3)
          geom.setAttribute('color', colorAttr)
        }

        setMesh({ geom: centered, colors: !!colors })
        setLoading(false)
      })
      .catch(err => {
        if (!cancelled) {
          setError(err.message)
          setLoading(false)
        }
      })

    return () => { cancelled = true }
  }, [plyUrl])

  if (loading) {
    return (
      <Html center>
        <div className="text-xs text-muted-foreground">Loading 3D model...</div>
      </Html>
    )
  }

  if (error) {
    return (
      <Html center>
        <div className="text-xs text-red-400">Failed to load model: {error}</div>
      </Html>
    )
  }

  if (!mesh) {
    return (
      <Html center>
        <div className="text-sm text-muted-foreground">
          Upload an image and run optimization to see the 3D preview
        </div>
      </Html>
    )
  }

  return (
    <mesh geometry={mesh.geom}>
      <meshStandardMaterial
        roughness={0.7}
        metalness={0.1}
        side={THREE.DoubleSide}
        vertexColors={mesh.colors}
        toneMapped={false}
      />
    </mesh>
  )
}

const CanvasInvalidator: React.FC = () => {
  const invalidate = useThree((s) => s.invalidate)
  useEffect(() => {
    invalidate()
  }, [invalidate])
  return null
}

export const ThreeDView: React.FC<ThreeDViewProps> = ({
  stlUrl,
  coloredPlyUrl,
  stackSegments,
  className,
}) => {
  return (
    <div className={cn('relative h-full w-full overflow-hidden rounded-lg', className)}>
      <Canvas
        frameloop="demand"
        dpr={[1, 1.5]}
        camera={{ position: [2, 2, 5], fov: 45, near: 0.1, far: 1000 }}
        gl={{ antialias: true, alpha: false, powerPreference: 'low-power', toneMapping: THREE.NoToneMapping }}
        onCreated={(state: any) => {
          state.gl.setClearColor(new THREE.Color('#0f1c2a'))
        }}
      >
        <CanvasInvalidator />
        <ambientLight intensity={1.1} />
        <hemisphereLight args={['#ffffff', '#334155', 0.6]} />
        <directionalLight position={[5, 10, 5]} intensity={0.4} />
        <directionalLight position={[-5, -5, -5]} intensity={0.25} />
        {coloredPlyUrl ? (
          <ColoredMesh plyUrl={coloredPlyUrl} />
        ) : stlUrl ? (
          <ColoredMesh plyUrl={stlUrl} />
        ) : stackSegments ? (
          <ColorStackPreview segments={stackSegments} />
        ) : null}
        <OrbitControls
          enablePan={true}
          enableZoom={true}
          enableRotate={true}
          minDistance={0.5}
          maxDistance={50}
          enableDamping={true}
          dampingFactor={0.05}
          onStart={() => { /* invalidate via CanvasInvalidator */ }}
          onChange={() => { /* invalidate via CanvasInvalidator */ }}
          onEnd={() => { /* invalidate via CanvasInvalidator */ }}
        />
      </Canvas>
    </div>
  )
}