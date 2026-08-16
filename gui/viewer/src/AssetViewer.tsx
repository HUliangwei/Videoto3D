import React, { useCallback, useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { TrackballControls } from 'three/examples/jsm/controls/TrackballControls.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { SparkRenderer, SplatMesh } from '@sparkjsdev/spark'

export type AssetType = 'glb' | 'splat'

export interface AssetViewerProps {
  type: AssetType
  src: string
  className?: string
  background?: string
  autoRotate?: boolean
  showToolbar?: boolean
}

type ViewName = 'Front' | 'Back' | 'Left' | 'Right' | 'Top' | 'Bottom' | 'Iso'
type Actions = {
  fit: () => void
  reset: () => void
  view: (name: ViewName) => void
  rotate: (enabled: boolean) => void
  roll: (degrees: number) => void
}

function disposeObject(object: THREE.Object3D) {
  object.traverse((child) => {
    const mesh = child as THREE.Mesh
    mesh.geometry?.dispose?.()
    const material = mesh.material as THREE.Material | THREE.Material[] | undefined
    const materials = Array.isArray(material) ? material : material ? [material] : []
    materials.forEach((item) => item.dispose())
  })
}

export function AssetViewer({ type, src, className, background = '#07090d', autoRotate = false, showToolbar = true }: AssetViewerProps) {
  const hostRef = useRef<HTMLDivElement>(null)
  const actionsRef = useRef<Actions>({ fit: () => {}, reset: () => {}, view: () => {}, rotate: () => {}, roll: () => {} })
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [error, setError] = useState('')
  const [rotating, setRotating] = useState(autoRotate)

  const enterFullscreen = useCallback(() => { hostRef.current?.requestFullscreen?.() }, [])
  useEffect(() => { setRotating(autoRotate); actionsRef.current.rotate(autoRotate) }, [autoRotate])

  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    setStatus('loading'); setError('')

    const scene = new THREE.Scene(); scene.background = new THREE.Color(background)
    const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 10000)
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false })
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2)); host.appendChild(renderer.domElement)

    const controls = new TrackballControls(camera, renderer.domElement)
    controls.rotateSpeed = 2.0; controls.zoomSpeed = 1.2; controls.panSpeed = 0.45
    controls.staticMoving = false; controls.dynamicDampingFactor = 0.14
    controls.mouseButtons.LEFT = THREE.MOUSE.ROTATE
    controls.mouseButtons.RIGHT = THREE.MOUSE.PAN
    controls.mouseButtons.MIDDLE = THREE.MOUSE.DOLLY
    controls.keys = ['', '', '']
    let autoRotateEnabled = autoRotate

    scene.add(new THREE.HemisphereLight(0xffffff, 0x223344, 2.1))
    const key = new THREE.DirectionalLight(0xffffff, 2.8); key.position.set(3, 5, 4); scene.add(key)

    let loadedObject: THREE.Object3D | null = null
    let splat: SplatMesh | null = null
    let spark: SparkRenderer | null = null
    let objectBox = new THREE.Box3()
    let center = new THREE.Vector3()
    let distance = 3

    const applyView = (name: ViewName) => {
      const dirs: Record<ViewName, THREE.Vector3> = {
        Front: new THREE.Vector3(0, 0, 1), Back: new THREE.Vector3(0, 0, -1),
        Left: new THREE.Vector3(-1, 0, 0), Right: new THREE.Vector3(1, 0, 0),
        Top: new THREE.Vector3(0, 1, 0), Bottom: new THREE.Vector3(0, -1, 0),
        Iso: new THREE.Vector3(0.8, 0.5, 1),
      }
      const dir = dirs[name].clone().normalize()
      const desiredUp = camera.up.clone().normalize()
      if (Math.abs(dir.dot(desiredUp)) > 0.98) desiredUp.set(0, 0, name === 'Bottom' ? 1 : -1)
      camera.up.copy(desiredUp)
      camera.position.copy(center).addScaledVector(dir, distance)
      controls.target.copy(center); camera.lookAt(center); controls.update()
    }

    const fitBox = (box: THREE.Box3) => {
      if (box.isEmpty()) return
      objectBox = box.clone(); center = box.getCenter(new THREE.Vector3())
      const size = box.getSize(new THREE.Vector3()); const maxDim = Math.max(size.x, size.y, size.z, 0.001)
      distance = (maxDim / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2))) * 1.55
      camera.near = Math.max(distance / 1000, 0.001); camera.far = Math.max(distance * 100, 100); camera.updateProjectionMatrix()
      applyView('Iso')
    }

    const rollCamera = (degrees: number) => {
      const viewAxis = controls.target.clone().sub(camera.position).normalize()
      if (viewAxis.lengthSq() === 0) return
      camera.up.applyAxisAngle(viewAxis, THREE.MathUtils.degToRad(degrees)).normalize()
      camera.lookAt(controls.target); controls.update()
    }

    actionsRef.current = {
      fit: () => fitBox(objectBox), reset: () => applyView('Iso'), view: applyView,
      rotate: (enabled) => { autoRotateEnabled = enabled },
      roll: rollCamera,
    }

    const focusFromDoubleClick = (event: MouseEvent) => {
      const rect = renderer.domElement.getBoundingClientRect()
      const pointer = new THREE.Vector2(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1)
      const raycaster = new THREE.Raycaster(); raycaster.setFromCamera(pointer, camera)
      const hits = raycaster.intersectObjects(scene.children, true)
      const hit = hits.find((item) => item.object !== spark)
      if (hit) { controls.target.copy(hit.point); controls.update() }
    }
    renderer.domElement.addEventListener('dblclick', focusFromDoubleClick)

    if (type === 'glb') {
      new GLTFLoader().load(src, (gltf) => {
        loadedObject = gltf.scene; scene.add(gltf.scene); fitBox(new THREE.Box3().setFromObject(gltf.scene)); setStatus('ready')
      }, undefined, (reason) => { console.error(reason); setError('GLB 加载失败'); setStatus('error') })
    } else {
      try {
        spark = new SparkRenderer({ renderer }); scene.add(spark)
        splat = new SplatMesh({ url: src, onLoad: (mesh) => {
          try { fitBox(mesh.getBoundingBox(true)) } catch { camera.position.set(2.4, 1.4, 3.2) }
          setStatus('ready')
        } }); scene.add(splat)
      } catch (reason) { console.error(reason); setError('Gaussian Splat 加载失败'); setStatus('error') }
    }

    const resize = () => { const w = Math.max(host.clientWidth, 1); const h = Math.max(host.clientHeight, 1); renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); controls.handleResize() }
    const observer = new ResizeObserver(resize); observer.observe(host); resize()
    let frame = 0
    const animate = () => {
      if (autoRotateEnabled && controls.target.distanceToSquared(camera.position) > 0) {
        const offset = camera.position.clone().sub(controls.target)
        const axis = camera.up.clone().normalize()
        offset.applyAxisAngle(axis, 0.0025)
        camera.position.copy(controls.target).add(offset); camera.lookAt(controls.target)
      }
      controls.update(); renderer.render(scene, camera); frame = requestAnimationFrame(animate)
    }; animate()

    return () => {
      cancelAnimationFrame(frame); observer.disconnect(); renderer.domElement.removeEventListener('dblclick', focusFromDoubleClick); controls.dispose()
      if (loadedObject) disposeObject(loadedObject)
      ;(splat as unknown as { dispose?: () => void } | null)?.dispose?.(); (spark as unknown as { dispose?: () => void } | null)?.dispose?.()
      renderer.dispose(); renderer.domElement.remove()
    }
  }, [type, src, background])

  const view = (name: ViewName) => actionsRef.current.view(name)
  const toggleRotate = () => { const next = !rotating; setRotating(next); actionsRef.current.rotate(next) }
  return <div ref={hostRef} className={className} style={{ position:'relative', width:'100%', height:'100%', overflow:'hidden' }}>
    {status === 'loading' && <div style={overlayStyle}>Loading {type.toUpperCase()}…</div>}
    {status === 'error' && <div style={overlayStyle}>{error}</div>}
    {showToolbar && <>
      <div style={toolbarStyle}>
        <button style={buttonStyle} onClick={() => actionsRef.current.fit()}>Fit</button><button style={buttonStyle} onClick={() => actionsRef.current.reset()}>Reset</button>
        {(['Front','Back','Left','Right','Top','Bottom','Iso'] as ViewName[]).map((name) => <button key={name} style={buttonStyle} onClick={() => view(name)}>{name}</button>)}
        <button style={buttonStyle} onClick={() => actionsRef.current.roll(-90)}>Roll Left</button><button style={buttonStyle} onClick={() => actionsRef.current.roll(180)}>Flip</button><button style={buttonStyle} onClick={() => actionsRef.current.roll(90)}>Roll Right</button>
        <button style={buttonStyle} onClick={toggleRotate}>Auto Rotate {rotating ? 'On' : 'Off'}</button><button style={buttonStyle} onClick={enterFullscreen}>Fullscreen</button>
      </div>
      <div style={hintStyle}>LMB Free Rotate/Roll · RMB Pan · Wheel Zoom · Double Click Focus</div>
    </>}
  </div>
}

const overlayStyle: React.CSSProperties = { position:'absolute', inset:0, zIndex:3, display:'grid', placeItems:'center', color:'rgba(255,255,255,.78)', font:'500 13px/1.4 Inter, system-ui, sans-serif', pointerEvents:'none', background:'radial-gradient(circle at center, rgba(17,22,30,.4), rgba(7,9,13,.85))' }
const toolbarStyle: React.CSSProperties = { position:'absolute', right:14, bottom:14, zIndex:4, display:'flex', flexWrap:'wrap', justifyContent:'flex-end', gap:6, maxWidth:'82%' }
const hintStyle: React.CSSProperties = { position:'absolute', left:14, bottom:14, zIndex:4, font:'500 10px/1.4 Inter, system-ui, sans-serif', color:'rgba(255,255,255,.55)', background:'rgba(8,11,16,.62)', border:'1px solid rgba(255,255,255,.1)', borderRadius:999, padding:'7px 10px', pointerEvents:'none' }
const buttonStyle: React.CSSProperties = { border:'1px solid rgba(255,255,255,.16)', borderRadius:999, padding:'7px 10px', color:'#f2f5f7', background:'rgba(8,11,16,.72)', backdropFilter:'blur(14px)', cursor:'pointer', fontSize:11 }
